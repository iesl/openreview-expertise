"""
Copyright (C) 2017-2018 University of Massachusetts Amherst.
This file is part of "learned-string-alignments"
http://github.com/iesl/learned-string-alignments
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://www.apache.org/licenses/LICENSE-2.0
Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

from collections import defaultdict

import numpy as np
import time
import csv
import sys, os
import random
import ast
from . import utils

csv.field_size_limit(sys.maxsize)

class Batcher(object):
    def __init__(self, input_file, batch_size=4, max_num_batches=None):
        self.data = []
        self.num_examples = 0
        self.max_num_batches = max_num_batches
        self.input_file = input_file
        self.batch_size = batch_size

        self.load_data(self.input_file)

    def reset(self):
        self.start_index = 0

    def shuffle_data(self):
        # perm = np.random.permutation(self.num_examples)
        print('shuffling {} lines via the following permutation'.format(self.num_examples))
        # data_array = np.asarray(self.data)
        # shuffled_data_array = data_array[perm]
        # self.data = shuffled_data_array.tolist()
        self.data = np.random.permutation(self.data).tolist()
        return self.data

    def load_data(self, input_file, delimiter='\t'):
        self.input_file = input_file

        self.data = []

        with open(input_file) as f:
            if any(input_file.endswith(ext) for ext in ['.tsv','.csv']):
                reader = csv.reader(f, delimiter=delimiter)
            elif input_file.endswith('.jsonl'):
                reader = utils.jsonl_reader(input_file)
            else:
                raise IOError('input file type must be .tsv, .csv, or .jsonl')

            for item in reader:
                self.data.append(item)

        self.num_examples = len(self.data)

    def batches(self, batch_size=None, delimiter='\t', transpose=False):
        if not batch_size:
            batch_size = self.batch_size

        num_batches_yielded = 0

        batch = []
        self.start_index = 0

        with open(self.input_file) as f:
            if self.input_file.endswith('.jsonl'):
                reader = utils.jsonl_reader(self.input_file)
            elif any(self.input_file.endswith(ext) for ext in ['.tsv','.csv']):
                reader = csv.reader(f, delimiter=delimiter)
            else:
                raise IOError('input file type must be .tsv, .csv, or .jsonl')

            for data in reader:
                batch.append(data)
                self.start_index += 1

                if self.start_index % batch_size == 0 or self.start_index == self.num_examples:
                    yield batch if not transpose else list(map(list, zip(*batch)))
                    num_batches_yielded += 1
                    batch = []

                if num_batches_yielded == self.max_num_batches:
                    break

