from abc import ABC
from typing import Union

import torch
from torch import Tensor
import torch.nn as nn
from transformers import RobertaConfig, RobertaModel, RobertaPreTrainedModel

from src.model.additive_attention import AdditiveAttention


class NewsEncoder(ABC, RobertaPreTrainedModel):
    def __init__(self, config: RobertaConfig, apply_reduce_dim: bool, use_cls_embed: bool, use_sapo: bool,
                 use_category: bool, category_pad_token_id: int, query_dim: int, dropout: float,
                 category_embed_dim: Union[int, None] = None, category_embed: Union[Tensor, None] = None,
                 num_category: Union[int, None] = None, num_cnn_filters: Union[int, None] = None,
                 window_size: Union[int, None] = None, word_embed_dim: Union[int, None] = None):
        r"""
        Initialization

        Args:
            config: the configuration of a ``RobertaModel``.
            apply_reduce_dim: whether to reduce the dimension of Roberta's embedding or not.
            use_cls_embed: whether to use the embedding of ``[CLS]`` token as a sequence embeddings or not.
            use_sapo: whether to use sapo embedding or not.
            use_category: whether to use category embedding or not.
            category_pad_token_id: ID of pad token in category dictionary.
            query_dim: size of query vector in the additive attention network.
            dropout: dropout value.
            category_embed_dim: size of each category vector.
            category_embed: pre-trained category embedding.
            num_category: size of category dictionary.
            num_cnn_filters: number of channels produced by the convolution in CNN network.
            window_size: size of the convolving kernel in CNN networks.
            word_embed_dim: size of each word embedding vector if ``apply_reduce_dim``.
        """
        super().__init__(config)
        self.roberta = RobertaModel(config)
        self.apply_reduce_dim = apply_reduce_dim

        if self.apply_reduce_dim:
            assert word_embed_dim is not None
            self.reduce_dim = nn.Linear(in_features=config.hidden_size, out_features=word_embed_dim)
            self.word_embed_dropout = nn.Dropout(dropout)
            self._embed_dim = word_embed_dim
        else:
            self._embed_dim = config.hidden_size

        self.use_cls_embed = use_cls_embed
        self.use_sapo = use_sapo
        self.use_category = use_category
        if not self.use_cls_embed:
            assert window_size is not None and num_cnn_filters is not None
            # Title encoder
            self.title_cnn = nn.Conv1d(in_channels=self._embed_dim, out_channels=num_cnn_filters,
                                       kernel_size=window_size, padding='same')
            self.title_dropout = nn.Dropout(dropout)
            self.title_additive_attn = AdditiveAttention(query_dim=query_dim, embed_dim=num_cnn_filters)

            # Sapo encoder
            if self.use_sapo:
                self.sapo_cnn = nn.Conv1d(in_channels=self._embed_dim, out_channels=num_cnn_filters,
                                          kernel_size=window_size, padding='same')
                self.sapo_dropout = nn.Dropout(dropout)
                self.sapo_additive_attn = AdditiveAttention(query_dim=query_dim, embed_dim=num_cnn_filters)

            self._embed_dim = num_cnn_filters

        # Category encoder
        if self.use_category:
            if category_embed is not None:
                self.category_embedding = nn.Embedding.from_pretrained(embeddings=category_embed, freeze=False,
                                                                       padding_idx=category_pad_token_id)
                category_embed_dim = category_embed.shape[1]
            else:
                assert num_category is not None
                self.category_embedding = nn.Embedding(num_embeddings=num_category, embedding_dim=category_embed_dim,
                                                       padding_idx=category_pad_token_id)

            self.category_dense_layer = nn.Sequential(
                nn.Linear(in_features=category_embed_dim, out_features=self._embed_dim),
                nn.ReLU()
            )

        # Attentive pooling
        if self.use_sapo or self.use_category:
            self.attn_pooling = AdditiveAttention(query_dim=query_dim, embed_dim=self._embed_dim)

        self.init_weights()

    def forward(self, title_encoding: Tensor, title_attn_mask: Tensor, sapo_encoding: Union[Tensor, None] = None,
                sapo_attn_mask: Union[Tensor, None] = None, category_encoding: Union[Tensor, None] = None):
        r"""
        Forward propagation

        Args:
            title_encoding: tensor of shape ``(batch_size, title_length)``.
            title_attn_mask: tensor of shape ``(batch_size, title_length)``.
            sapo_encoding: tensor of shape ``(batch_size, sapo_length)``.
            sapo_attn_mask: tensor of shape ``(batch_size, sapo_length)``.
            category_encoding: tensor of shape ``(batch_size)``.

        Returns:
            Tensor of shape ``(batch_size, embed_dim)``
        """
        news_info = []
        # Title encoder
        title_word_embed = self.roberta(input_ids=title_encoding, attention_mask=title_attn_mask)[0]
        if self.apply_reduce_dim:
            title_word_embed = self.reduce_dim(title_word_embed)
            title_word_embed = self.word_embed_dropout(title_word_embed)
        if self.use_cls_embed:
            title_repr = title_word_embed[:, 0, :]
        else:
            title_word_embed = title_word_embed.transpose(1, 2).contiguous()
            title_word_context = self.title_cnn(title_word_embed)
            title_word_context = title_word_context.transpose(1, 2).contiguous()
            title_word_context = self.title_dropout(title_word_context)
            title_repr = self.title_additive_attn(embeddings=title_word_context, mask=title_attn_mask)
        news_info.append(title_repr)

        # Sapo encoder
        if self.use_sapo:
            sapo_word_embed = self.roberta(input_ids=sapo_encoding, attention_mask=sapo_attn_mask)[0]
            if self.apply_reduce_dim:
                sapo_word_embed = self.reduce_dim(sapo_word_embed)
                sapo_word_embed = self.word_embed_dropout(sapo_word_embed)
            if self.use_cls_embed:
                sapo_repr = sapo_word_embed[:, 0, :]
            else:
                sapo_word_embed = sapo_word_embed.transpose(1, 2).contiguous()
                sapo_word_context = self.sapo_cnn(sapo_word_embed)
                sapo_word_context = sapo_word_context.transpose(1, 2).contiguous()
                sapo_word_context = self.sapo_dropout(sapo_word_context)
                sapo_repr = self.sapo_additive_attn(embeddings=sapo_word_context, mask=sapo_attn_mask)

            news_info.append(sapo_repr)

        # Category encoder
        if self.use_category:
            category_embed = self.category_embedding(category_encoding)
            category_repr = self.category_dense_layer(category_embed)
            news_info.append(category_repr)

        # Attentive pooling
        if self.use_category or self.use_sapo:
            news_info = torch.stack(news_info, dim=1)
            mask = torch.ones((news_info.shape[0], news_info.shape[1]), dtype=torch.bool, device=news_info.device)

            return self.attn_pooling(embeddings=news_info, mask=mask)
        else:
            return title_repr

    @property
    def embed_dim(self):
        return self._embed_dim
