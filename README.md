# README

Code for **Neural News Recommendation with Attentive Multi-View Learning**. Please see 
[the paper](https://arxiv.org/pdf/1907.05576).

![](./assets/model.png)

## Setup
### Requirements


### Dataset
The datasets used in my experiments: [link](https://drive.google.com/file/d/1QvtKukmitPtV7Mhu3R-eOBNexHWljUtf/view?usp=sharing) 


| File Name           | Description                                                           |
|---------------------|-----------------------------------------------------------------------|
| news.tsv            | The information of news articles                                      |
| train_behaviors.tsv | The click histories and impression logs of users for training phase   |
| valid_behaviors.tsv | The click histories and impression logs of users for validation phase |
| test_behaviors.tsv  | The click histories and impression logs of users for test phase       |
| category2id.json    | Mapping the category of news to id                                    |
| user2id.json        | Mapping the user to id                                                |

The **\*_behaviors.tsv** file contains the impression logs and users' news click histories. 
It has 5 columns divided by the tab symbol:

* **Impression ID**: The ID of an impression.
* **User ID**: The ID of a user.
* **Time**: The impression time with format "MM/DD/YYYY HH:MM:SS AM/PM".
* **History**: The news click history (ID list of clicked news) of this user before this impression. The clicked news 
articles are ordered by time.
* **Impressions**: List of news displayed in this impression and user's click behaviors on them (1 for click and 0 
for non-click). The orders of news in an impressions
have been shuffled.

The **news.tsv** file contains the detailed information of news articles involved in the **\*_behaviors.tsv** file.
It has 4 columns, which are divided by the tab symbol:

* **News ID** 
* **Title** 
* **Category**
* **Sapo**


## Training
Download the data and save it in ```data/```.


Single GPU training:

``` shell
python main.py train @config/train.txt
```