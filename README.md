# Paper-reviewer affinity modeling for OpenReview

A key part of matching papers to reviewers is having a good model of paper-reviewer affinity. This repository holds code and tools for generating affinity scores between papers and reviewers.

## Installation

This repository only supports Python 3.6 and above.
Clone this repository and install the package using pip as follows. If you plan to use ELMo, then you will need to install [Miniconda](https://docs.conda.io/en/latest/miniconda.html), since one of the packages is only available in conda. You may use the `pip` command in a conda environment as long as you first run all the pip installs and then conda installs. Just follow the order of the commands shown below and it should work. You may read more about this [here](https://www.anaconda.com/using-pip-in-a-conda-environment/).

Run this command only if you are using conda:
```
conda create -n affinity python=3.7
conda activate affinity
conda install pip
```

```
pip install <location of this repository>
```

If you plan to actively develop models, it's best to install the package in "edit" mode, so that you don't need to reinstall the package every time you make changes:

```
pip install -e <location of this repository>
```

Because some of the libraries are specific to our operating system you would need to install these dependencies separately. We expect to improve this in the future. If you plan to use ELMo with GPU you need to install [pytorch](https://pytorch.org/) by selecting the right configuration for your particular OS, otherwise, if you are only using the CPU, the current dependencies should be fine. We also use [faiss](https://github.com/facebookresearch/faiss/) for ELMo to calculate vector similarities. This is not included in the dependencies inside `setup.py` because the official package is only available in conda.

Run this command if you plan to use ELMo (Using CPU is fine):
```
conda install faiss-cpu -c pytorch
```
[Here](https://github.com/facebookresearch/faiss/blob/master/INSTALL.md) you can find the above installation command.

## Run

There are two steps to create affinity scores:
- Create Dataset
- Run Model.

The dataset is generated using the [OpenReview python API](https://github.com/openreview/openreview-py) which should be installed when this repository is installed. You can generate your own dataset from some other source as long as it is compliant with the format shown in the Datasets section.
Start by creating an "experiment directory" (`experiment_dir`), and a JSON config file (e.g. `config.json`) in it. Go to the Configuration File section for details on how to create the `config.json`.

Create a dataset by running the following command:
```
python -m expertise.create_dataset config.json \
	--baseurl <usually https://openreview.net> \
	--password <your_password> \
	--username <your_username> \
```

For ELMo and BM25 run the following command
```
python -m expertise.run config.json
```
The output will generate a `.csv` file with the name pattern `<config_name>.csv`.

For TF-IDF Sparse Vector Similarity run the following command:
```
python -m expertise.tfidf_scores config.json
```

The output will generate a `.csv` file with the name pattern `<config_name>-scores.csv`.


## Configuration File

The configuration file or `config.json` is the file that contains all the parameters to calculate affinity scores.
Below you will find examples of possible configurations depending on the Model that you want to use. You may have a config file for creating the dataset and another for generating the affinity scores, something like `dataset-config.json` and `affinity-config.json`. However you can have everything in a single file like in the examples below:

### Create Dataset Configuration Options
This parameters could be included in a separate file, like `dataset-config.json`, as was mentioned before.
- `match_group`: String or array of strings containing the groups of Reviewers or Area Chairs. The Reviewers (and Area Chairs) will get affinity scores with respect to the submitted papers based on their expertise. This expertise is obtained based on the publications available in OpenReview.
- `paper_invitation`: String or array of strings with the submission invitations. This is the invitation for Submissions, all the submissions in OpenReview for a particular venue have an invitation and that is how they are grouped together.
- `exclusion_inv`: String or array of strings with the exclusion invitations. Reviewers (and Area Chairs) can choose to exclude some of their papers before the affinity scores are calculated so that they get papers that are more aligned to their current expertise/interest. Papers included here will not be taken into consideration when calculating the affinity scores.
- `bid_inv`: String or array of strings with the bid invitations. Bids are used by the reviewers in OpenReview to select papers that they would or would not like to review. These bids are then used to compute a final affinity score to be more fair with the reviewers.
- `dataset.directory`: This is the directory where the data will be dumped. Once `create_dataset` finishes running, all the folders with the files inside will be in there.

### Affinity Scores Configuration Options
These parameters could be included in a separate file, like `affinity-config.json`, as was mentioned before.

- `name`: This is the name that the `.csv` file containing the affinity scores will have.
- `model_params.scores_path`: This is the directory where the `.csv` file with the scores will be dumped.
- `model_params.use_title`: Boolean that indicates whether to use the title for the affinity scores or not. If this is `true` then `model_params.use_abstract` must be `false`.
- `model_params.use_abstract`: Boolean that indicates whether to use the abstract for the affinity scores or not. If this is `true` then `model_params.use_title` must be `false`.

#### BM25Okapi specific parameters:
- `model_params.workers`: This is the number of processes that for BM25Okapi. This depends on your machine, but 4 is usually a safe value.

Here is an example:
```
{
    "name": "iclr2020_bm25_abstracts",
    "match_group": ["ICLR.cc/2020/Conference/Reviewers", "ICLR.cc/2020/Conference/Area_Chairs"],
    "paper_invitation": "ICLR.cc/2020/Conference/-/Blind_Submission",
    "exclusion_inv": "ICLR.cc/2020/Conference/-/Expertise_Selection",
    "bid_inv": "ICLR.cc/2020/Conference/-/Add_Bid",
    "dataset": {
        "directory": "./"
    },
    "model": "bm25",
    "model_params": {
        "scores_path": "./",
        "use_title": false,
        "use_abstract": true,
        "workers": 4,
        "publications_path": "./",
        "submissions_path": "./"
    }
}
```

#### ELMo specific parameters:
- `model_params.use_cuda`: Boolean to indicate whether to use GPU (`true`) or CPU (`false`) when running ELMo. Currently, only 1 GPU is supported, but there does not seem to be necessary to have more.
- `model_params.batch_size`: Batch size when running ELMo. This defaults to 8, but depending on your machine, this value could be different.
- `model_params.publications_path`: When running ELMo, this is where the embedded abstracts/titles of the Reviewers (and Area Chairs) are stored.
- `model_params.submissions_path`: When running ELMo, this is where the embedded abstracts/titles of the Submissions are stored.
- `model_params.publications_path`: When running ELMo, this is where the embedded abstracts/titles of the Reviewers (and Area Chairs) are stored.
- `model_params.submissions_path`: When running ELMo, this is where the embedded abstracts/titles of the Submissions are stored.
- `model_params.knn`: This parameter specifies the k Nearest Neighbors that will be printed to the csv file. For instance, if the value is 10, then only the first 10 authors with the highest affinity score will be printed for each submission. You may see that if the value is 10, more than 10 values are printed, that is because there are ties in the scores.
- `model_params.skip_elmo`: Since running ELMo can take a significant amount of time, the vectors are saved in `model_params.submissions_path` and `model_params.publications_path`. If you want to run other operations with these results, like changing the value of `model_params.knn`, you may do so without running ELMo again by setting `model_params.skip_elmo` to true. The pickle files will be loaded with all the vectors.

Here is an example:
```
{
    "name": "iclr2020_elmo_abstracts",
    "match_group": ["ICLR.cc/2020/Conference/Reviewers", "ICLR.cc/2020/Conference/Area_Chairs"],
    "paper_invitation": "ICLR.cc/2020/Conference/-/Blind_Submission",
    "exclusion_inv": "ICLR.cc/2020/Conference/-/Expertise_Selection",
    "bid_inv": "ICLR.cc/2020/Conference/-/Add_Bid",
    "dataset": {
        "directory": "./"
    },
    "model": "elmo",
    "model_params": {
        "scores_path": "./",
        "use_title": false,
        "use_abstract": true,
        "use_cuda": true,
        "batch_size": 8,
        "skip_elmo": false,
        "knn": 500,
        "publications_path": "./",
        "submissions_path": "./"
    }
}
```

#### TF-IDF Sparse Vector Similarity specific parameters with suggested values:
- `min_count_for_vocab`: 1,
- `random_seed`: 9,
- `max_num_keyphrases`: 25,
- `do_lower_case`: true,
- `experiment_dir`: "./"

Here is an example:

```
{
    "name": "iclr2020_reviewers_tfidf",
    "match_group": ["ICLR.cc/2020/Conference/Reviewers", "ICLR.cc/2020/Conference/Area_Chairs"],
    "paper_invitation": "ICLR.cc/2020/Conference/-/Blind_Submission",
    "exclusion_inv": "ICLR.cc/2020/Conference/-/Expertise_Selection",
    "min_count_for_vocab": 1,
    "random_seed": 9,
    "max_num_keyphrases": 25,
    "do_lower_case": true,
    "dataset": {
        "directory": "./"
    },
    "experiment_dir": "./"
}
```

## Datasets

The framework expects datasets to adhere to a specific format. Each dataset directory should be structured as follows:

```
dataset-name/
	archives/
		~User_Id1.jsonl 		# user's tilde IDs
		~User_Id2.jsonl
		...
	submissions/
		aBc123XyZ.jsonl 		# paper IDs
		ZYx321Abc.jsonl
		...
	bids/
		aBc123XyZ.jsonl 		# should have same IDs as /submissions
		ZYx321Abc.jsonl
		...

```

The `archives` folder will contain the user ids of people that will review papers. The reviewers should have publications for the affinity scores to be calculated. For example, the `~User_Id1.jsonl` file will contain all the his publications.

The `submissions` folder conatins all the submissions of a particular venue. The name of the file is the id used to identify the submission in OpenReview. Each file will only contain one line with all the submission content.

The files in both `archives` and `submissions` should contain stringified JSONs that should have the following schema to work:
```
{
    id: <unique-id>,
    content: {
        title: <some-title>,
        abstract: <some-abstract>
    }
}
```
Other fields are allowed, but this is what the code will be looking for.

The `bids` folder is usually not necessary to compute affinity scores. Bids are used by the reviewers in OpenReview to select papers that they would or would not like to review. These bids are then used to compute a final affinity score to be more fair with the reviewers.

Some datasets differ slightly in terms of the format of the data; these should be accounted for in the experiment's configuration.

Some older conferences use a bidding format that differs from the default "Very High" to "Very Low" scale. This can be parameterized in the `config.json` file (e.g.) as follows:

```
{
    "name": "uai18-tfidf",
    "dataset": {
        "directory": "/path/to/uai18/dataset",
        "bid_values": [
            "I want to review",
            "I can review",
            "I can probably review but am not an expert",
            "I cannot review",
            "No bid"
        ],
        "positive_bid_values": ["I want to review", "I can review"]
    },
    ...
}

```

## Test
The testing methodology used for the model tries to check how good the model is. We are aware that this may not be the best strategy, but it has given good results so far. The test consists on using the publications of several reviewers and take one of those publications out from the corpus. We then use that extracted publication to calculate affinity scores against the remaining publications in the corpus. If the model is good then, we expect the authors of the extracted publication to have the highest affinity scores.

This method has two obvious disadvantages:
- It only works if the author has at least two publications.
- It also assumes that all the publications of an author (or at least two of them) are very similar.

So far, we have seen that the last assumption seems to be true. We tested this on ~50,000 publications. Here are some results:

|First | ELMo | BM25 |
| ---- | ---- |----- |
| 1    |0.383 |0.318 |
| 5    |0.485 |0.486 |
| 10   |0.516 |0.538 |
| 100  |0.671 |0.735 |

This table shows that 38.3% of the time ELMo gets the author of the paper as the best ranked. Likewise, 31.8% of the time BM25 gets the author of the paper as the best ranked. We will conduct more tests in the future.
