import openreview
import os, sys
import json
import itertools
import multiprocessing as mp
import random
from datetime import datetime
from expertise.models import tfidf, model_utils
import argparse

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('score_file', help='name of the score file')
    parser.add_argument('submission_records_dir', help='directory with .jsonl files representing submission records')
    parser.add_argument('reviewer_records_dir', help='directory with .jsonl files representing reviewer "archives" (series of records representing their expertise)')
    parser.add_argument('--baseurl', help="openreview base url")
    parser.add_argument('--username')
    parser.add_argument('--password')
    args = parser.parse_args()

    client = openreview.Client(baseurl=args.baseurl, username=args.username, password=args.password)

    papers = client.get_notes(invitation='auai.org/UAI/2018/-/Blind_Submission')
    reviewers = client.get_group('auai.org/UAI/2018/Program_Committee')

    paper_content_by_id = {}
    for paper in papers:
        with open(os.path.join(args.submission_records_dir, paper.id + '.jsonl')) as f:
            paper_record = f.read()
            paper_content_by_id[paper.id] = json.loads(paper_record)['content']

    reviewer_content_by_id = {}
    for reviewer_id in reviewers.members:
        with open(os.path.join(args.reviewer_records_dir, reviewer_id + '.jsonl')) as f:
            contents = [json.loads(r.replace('\n',''))['content'] for r in f.readlines()]
            reviewer_content_by_id[reviewer_id] = contents

    print('fitting model')

    model = tfidf.Model()
    model_name = 'tfidf'

    all_content = paper_content_by_id.values()
    for content_list in reviewer_content_by_id.values():
        all_content = itertools.chain([content for content in content_list], all_content)

    model.fit(all_content)

    def get_best_score_pool(paper_reviewer):
        paper_id, reviewer_id = paper_reviewer
        best_score = 0.0

        paper_text = model_utils.content_to_text(paper_content_by_id[paper_id])

        reviewer_text_list = [model_utils.content_to_text(c) for c in reviewer_content_by_id[reviewer_id]]

        for reviewer_text in reviewer_text_list:
            score = model.score(reviewer_text, paper_text)
            if score > best_score:
                best_score = score

        return (paper_id, reviewer_id, best_score)


    start_time = datetime.now()

    open_type = 'w'
    existing_cells = []
    if os.path.isfile(args.score_file):
        open_type = 'a'
        with open(args.score_file) as f:
            lines = f.readlines()
            for line in lines:
                existing_cell = eval(line.replace('\n',''))
                existing_paper_reviewer = (existing_cell[0], existing_cell[1])
                existing_cells.append(existing_paper_reviewer)

    paper_reviewer_pairs = []
    for paper in papers:
        for reviewer_id in reviewers.members:
            if (paper.id, reviewer_id) not in existing_cells:
                paper_reviewer_pairs.append((paper.id, reviewer_id))

    print('starting pool on {} pairs at {}'.format(len(paper_reviewer_pairs), start_time))
    # start 4 worker processes
    with open(args.score_file, open_type) as f:
        pool = mp.Pool(processes=4)
        for result in pool.imap(get_best_score_pool, paper_reviewer_pairs):
            f.write('{}\n'.format(result))

    print('finished job in {}'.format(datetime.now() - start_time))
