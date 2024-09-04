from setuptools import setup

setup(
    name='openreview-expertise',
    version='1.0',
    description='OpenReview paper-reviewer affinity modeling',
    url='https://github.com/iesl/openreview-evidence',
    author='Michael Spector, Carlos Mondragon',
    author_email='spector@cs.umass.edu, carlos@openreview.net',
    license='MIT',
    packages=[
        'expertise'
    ],
    install_requires=[
        'openreview-py>=1.0.1',
        'numpy==1.24.4',
        'scipy==1.10.1',
        'pandas',
        'nltk',
        'gensim==4.1.2',
        'torch',
        'cloudpickle',
        'scikit-learn',
        'tqdm',
        'pytorch_pretrained_bert',
        'ipdb',
        'en_core_web_sm@https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-2.1.0/en_core_web_sm-2.1.0.tar.gz ',
        'python-Levenshtein',
        'tokenizers==0.13.3',
        'sacremoses',
        'rank_bm25',
        'pytest',
        'overrides==2.8.0',
        'flask==2.2.2',
        'flask-cors==3.0.9',
        'cffi>=1.0.0',
        'celery==5.2.7',
        "kombu>=5.3.0,<6.0",
        'redis',
        'pytest-celery',
        'shortuuid',
        'redisai',
        'python-dotenv',
        'importlib-metadata==4.13.0',
        'werkzeug==2.2.2',
        'adapter-transformers==3.2.1.post0'
    ],
    zip_safe=False
)
