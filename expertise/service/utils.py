import openreview
import shortuuid
import os
import time
import json
import re
import redis, pickle
from unittest.mock import MagicMock
from enum import Enum

import re
REDIS_ADDR = 'localhost'
REDIS_PORT = 6379
REDIS_DB = 10
SUPERUSER_IDS = ['openreview.net']

# -----------------
# -- Mock Client --
# -----------------
def mock_client(version=1):
    client = MagicMock(openreview.Client)

    def get_user():
        return {
            'user': {
                'id': 'test_user1@mail.com'
            }
        }

    def get_token():
        return None

    def get_note(id):
        if version == 1:
            with open('tests/data/fakeData.json') as json_file:
                data = json.load(json_file)
        elif version == 2:
            with open('tests/data/api2Data.json') as json_file:
                data = json.load(json_file)
        else:
            raise openreview.OpenReviewException('Version number not supported')

        for invitation in data['notes'].keys():
            for note in data['notes'][invitation]:
                if note['id'] == id:
                    return openreview.Note.from_json(note)
        raise openreview.OpenReviewException({'name': 'NotFoundError', 'message': f"The Note {id} was not found", 'status': 404, 'details': {'path': 'id', 'value': id}})

    def get_profile(email_or_id = None):
        mock_profile = {
            "id": "~Test_User1",
            "content": {
                "preferredEmail": "Test_User1@mail.com",
                "emails": [
                    "Test_User1@mail.com"
                ]
            }
        }
        if email_or_id:
            tildematch = re.compile('~.+')
            if tildematch.match(email_or_id):
                att = 'id'
            else:
                att = 'email'
            with open('tests/data/fakeData.json') as json_file:
                data = json.load(json_file)
            profiles = data['profiles']
            for profile in profiles:
                profile = openreview.Profile.from_json(profile)
                if att == 'id':
                    if profile.id == email_or_id:
                        return profile
                else:
                    if email_or_id in profile.content.get('emails'):
                        return profile
        return openreview.Profile.from_json(mock_profile)

    def get_notes(id = None,
        paperhash = None,
        forum = None,
        original = None,
        invitation = None,
        replyto = None,
        tauthor = None,
        signature = None,
        writer = None,
        trash = None,
        number = None,
        content = None,
        limit = None,
        offset = None,
        mintcdate = None,
        details = None,
        sort = None):

        if offset != 0:
            return []
        if version == 1:
            with open('tests/data/expertiseServiceData.json') as json_file:
                data = json.load(json_file)
        elif version == 2:
            with open('tests/data/api2Data.json') as json_file:
                data = json.load(json_file)
        else:
            raise openreview.OpenReviewException('Version number not supported')

        if invitation:
            notes=data['notes'][invitation]
            return [openreview.Note.from_json(note) for note in notes]

        if 'authorids' in content:
            authorid = content['authorids']
            profiles = data['profiles']
            for profile in profiles:
                if authorid == profile['id']:
                    return [openreview.Note.from_json(note) for note in profile['publications']]

        return []

    def get_group(group_id):
        if version == 1:
            with open('tests/data/expertiseServiceData.json') as json_file:
                data = json.load(json_file)
        elif version == 2:
            with open('tests/data/api2Data.json') as json_file:
                data = json.load(json_file)
        else:
            raise openreview.OpenReviewException('Version number not supported')
        group = openreview.Group.from_json(data['groups'][group_id])
        return group

    def search_profiles(confirmedEmails=None, ids=None, term=None):
        if version == 1:
            with open('tests/data/expertiseServiceData.json') as json_file:
                data = json.load(json_file)
        elif version == 2:
            with open('tests/data/api2Data.json') as json_file:
                data = json.load(json_file)
        else:
            raise openreview.OpenReviewException('Version number not supported')
        profiles = data['profiles']
        profiles_dict_emails = {}
        profiles_dict_tilde = {}
        for profile in profiles:
            profile = openreview.Profile.from_json(profile)
            if profile.content.get('emails') and len(profile.content.get('emails')):
                profiles_dict_emails[profile.content['emails'][0]] = profile
            profiles_dict_tilde[profile.id] = profile
        if confirmedEmails:
            return_value = {}
            for email in confirmedEmails:
                if profiles_dict_emails.get(email, False):
                    return_value[email] = profiles_dict_emails[email]

        if ids:
            return_value = []
            for tilde_id in ids:
                return_value.append(profiles_dict_tilde[tilde_id])
        return return_value

    client.get_notes = MagicMock(side_effect=get_notes)
    client.get_note = MagicMock(side_effect=get_note)
    client.get_group = MagicMock(side_effect=get_group)
    client.search_profiles = MagicMock(side_effect=search_profiles)
    client.get_profile = MagicMock(side_effect=get_profile)
    client.get_user = MagicMock(side_effect=get_user)
    client.user = {
        'user': {
            'id': 'test_user1@mail.com'
        }
    }
    client.token = None

    return client
# -----------------
# -- Mock Client --
# -----------------

def get_user_id(openreview_client):
    """
    Returns the user id from an OpenReview client for authenticating access

    :param openreview_client: A logged in client with the user credentials
    :type openreview_client: openreview.Client

    :returns id: The id of the logged in user
    """
    user = openreview_client.user
    return user.get('user', {}).get('id') if user else None

def _get_required_field(req, superkey, key):
    try:
        field = req.pop(key)
    except KeyError:
        raise openreview.OpenReviewException(f"Bad request: required field missing in {superkey}: {key}")
    return field

class JobStatus(str, Enum):
    INITIALIZED = 'Initialized'
    QUEUED = 'Queued'
    FETCHING_DATA  = 'Fetching Data'
    EXPERTISE_QUEUED = 'Queued for Expertise'
    RUN_EXPERTISE = 'Running Expertise'
    COMPLETED = 'Completed'
    ERROR = 'Error'

class JobDescription(dict, Enum):
    VALS = {
        JobStatus.INITIALIZED: 'Server received config and allocated space',
        JobStatus.QUEUED: 'Job is waiting to start fetching OpenReview data',
        JobStatus.FETCHING_DATA: 'Job is currently fetching data from OpenReview',
        JobStatus.EXPERTISE_QUEUED: 'Job has assembled the data and is waiting in queue for the expertise model',
        JobStatus.RUN_EXPERTISE: 'Job is running the selected expertise model to compute scores',
        JobStatus.COMPLETED: 'Job is complete and the computed scores are ready',
    }
class APIRequest(object):
    """
    Validates and load objects and fields from POST requests
    """
    def __init__(self, request):
            
        self.entityA = {}
        self.entityB = {}
        self.model = {}
        root_key = 'request'

        def _get_field_from_request(field):
            return _get_required_field(request, root_key, field)

        def _load_entity_a(entity):
            self._load_entity('entityA', entity, self.entityA)

        def _load_entity_b(entity):
            self._load_entity('entityB', entity, self.entityB)

        # Get the name of the job
        self.name = _get_field_from_request('name')

        # Validate entityA and entityB
        entity_a = _get_field_from_request('entityA')
        entity_b = _get_field_from_request('entityB')

        _load_entity_a(entity_a)
        _load_entity_b(entity_b)

        # Optionally check for model object
        self.model = request.pop('model', {})

        # Check for empty request
        if len(request.keys()) > 0:
            raise openreview.OpenReviewException(f"Bad request: unexpected fields in {root_key}: {list(request.keys())}")
    
    def _load_entity(self, entity_id, source_entity, target_entity):
        '''Load information from an entity into the config'''
        def _get_from_entity(key):
            return _get_required_field(source_entity, entity_id, key)

        type = _get_from_entity('type')
        target_entity['type'] = type
        # Handle type group
        if type == 'Group':
            if 'memberOf' in source_entity.keys():
                target_entity['memberOf'] = _get_from_entity('memberOf')
                # Check for optional expertise field
                if 'expertise' in source_entity.keys():
                    target_entity['expertise'] = source_entity.pop('expertise')
            else:
                raise openreview.OpenReviewException(f"Bad request: no valid {type} properties in {entity_id}")
        # Handle type note
        elif type == 'Note':
            if 'invitation' in source_entity.keys() and 'id' in source_entity.keys():
                raise openreview.OpenReviewException(f"Bad request: only provide a single id or single invitation in {entity_id}")

            if 'invitation' in source_entity.keys():
                target_entity['invitation'] = _get_from_entity('invitation')
            elif 'id' in source_entity.keys():
                target_entity['id'] = _get_from_entity('id')
            else:
                raise openreview.OpenReviewException(f"Bad request: no valid {type} properties in {entity_id}")
        else:
            raise openreview.OpenReviewException(f"Bad request: invalid type in {entity_id}")

        # Check for extra entity fields
        if len(source_entity.keys()) > 0:
            raise openreview.OpenReviewException(f"Bad request: unexpected fields in {entity_id}: {list(source_entity.keys())}")
        
    def to_json(self):
        body = {
            'name': self.name,
            'entityA': self.entityA,
            'entityB': self.entityB,
        }
        if len(self.model.keys()) > 0:
            body['model'] = self.model

        return body

class JobConfig(object):
    """
    Helps translate fields from API requests to fields usable by the expertise system
    """
    def __init__(self,
        name=None,
        user_id=None,
        job_id=None,
        baseurl=None,
        baseurl_v2=None,
        job_dir=None,
        cdate=None,
        mdate=None,
        status=None,
        description=None,
        match_group=None,
        alternate_match_group=None,
        dataset=None,
        model=None,
        exclusion_inv=None,
        paper_invitation=None,
        paper_id=None,
        model_params=None):
        
        self.name = name
        self.user_id = user_id
        self.job_id = job_id
        self.baseurl = baseurl
        self.baseurl_v2 = baseurl_v2
        self.job_dir = job_dir
        self.cdate = cdate
        self.mdate = mdate
        self.status = status
        self.description = description
        self.match_group = match_group
        self.alternate_match_group = alternate_match_group
        self.dataset = dataset
        self.model = model
        self.exclusion_inv = exclusion_inv
        self.paper_invitation = paper_invitation
        self.paper_id = paper_id
        self.model_params = model_params

        self.api_request = None

    def to_json(self):
        pre_body = {
            'name': self.name,
            'user_id': self.user_id,
            'job_id': self.job_id,
            'baseurl': self.baseurl,
            'baseurl_v2': self.baseurl_v2,
            'job_dir': self.job_dir,
            'cdate': self.cdate,
            'mdate': self.mdate,
            'match_group': self.match_group,
            'alternate_match_group': self.alternate_match_group,
            'dataset': self.dataset,
            'model': self.model,
            'exclusion_inv': self.exclusion_inv,
            'paper_invitation': self.paper_invitation,
            'paper_id': self.paper_id,
            'model_params': self.model_params
        }

        # Remove objects that are none
        body = {}
        body_items = pre_body.items()
        for key, val in body_items:
            # Allow a None token
            if val is not None or key == 'token':
                body[key] = val

        return body

    def save(self):
        # Modify Redis keys with matchable prefix
        db = JobConfig._init_redis()
        db.set(f"job:{self.job_id}", pickle.dumps(self))
    
    def load_all_jobs(user_id):
        """
        Searches all keys for configs with matching user id
        If a Redis entry exists but the files do not, remove the entry from Redis and do not return this job
        Returns empty list if no jobs found
        """
        db = JobConfig._init_redis()
        configs = []

        for job_key in db.scan_iter("job:*"):
            current_config = pickle.loads(db.get(job_key))

            if not os.path.isdir(current_config.job_dir):
                print(f"No files found {job_key} - skipping")
                JobConfig.remove_job(user_id, current_config.job_id)
                continue

            if current_config.user_id == user_id or user_id in SUPERUSER_IDS:
                configs.append(current_config)

        return configs

    def load_job(job_id, user_id):
        """
        Retrieves a config based on job id
        """
        db = JobConfig._init_redis()
        job_key = f"job:{job_id}"

        if not db.exists(job_key):
            raise openreview.OpenReviewException('Job not found')        
        config = pickle.loads(db.get(job_key))
        if not os.path.isdir(config.job_dir):
            JobConfig.remove_job(user_id, job_id)
            raise openreview.OpenReviewException('Job not found')

        if config.user_id != user_id and user_id not in SUPERUSER_IDS:
            raise openreview.OpenReviewException('Forbidden: Insufficient permissions to access job')

        return config
    
    def remove_job(user_id, job_id):
        db = JobConfig._init_redis()
        job_key = f"job:{job_id}"

        if not db.exists(job_key):
            raise openreview.OpenReviewException('Job not found')
        config = pickle.loads(db.get(job_key))
        if config.user_id != user_id and user_id not in SUPERUSER_IDS:
            raise openreview.OpenReviewException('Forbidden: Insufficient permissions to modify job')

        db.delete(job_key)
        return config

    def _init_redis():
        db = redis.Redis(
            host = REDIS_ADDR,
            port = REDIS_PORT,
            db = REDIS_DB
        )
        return db

    def from_request(api_request: APIRequest,
        starting_config = {},
        openreview_client = None,
        server_config = {},
        working_dir = None):
        """
        Sets default fields from the starting_config and attempts to override from api_request fields
        """
        def _camel_to_snake(camel_str):
            camel_str = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', camel_str)
            return re.sub('([a-z0-9])([A-Z])', r'\1_\2', camel_str).lower()

        descriptions = JobDescription.VALS.value
        config = JobConfig()

        # Set metadata fields from request
        config.name = api_request.name
        config.user_id = get_user_id(openreview_client)
        config.job_id = shortuuid.ShortUUID().random(length=5)
        config.baseurl = server_config['OPENREVIEW_BASEURL']
        config.baseurl_v2 = server_config['OPENREVIEW_BASEURL_V2']
        config.api_request = api_request    

        root_dir = os.path.join(working_dir, config.job_id)
        config.dataset = starting_config.get('dataset', {})
        config.dataset['directory'] = root_dir
        config.job_dir = root_dir
        config.cdate = int(time.time() * 1000)
        config.mdate = config.cdate
        config.status = JobStatus.INITIALIZED.value
        config.description = descriptions[JobStatus.INITIALIZED]

        # Handle Group cases
        config.match_group = starting_config.get('match_group', None)
        config.alternate_match_group = starting_config.get('alternate_match_group', None)

        if api_request.entityA['type'] == 'Group':
            config.match_group = [api_request.entityA['memberOf']]
        if api_request.entityB['type'] == 'Group':
            config.alternate_match_group = [api_request.entityB['memberOf']]

        # Handle Note cases
        config.paper_invitation = None
        config.paper_id = None
        config.exclusion_inv = None

        if api_request.entityA['type'] == 'Note':
            inv, id = api_request.entityA.get('invitation', None), api_request.entityA.get('id', None)
            excl_inv = api_request.entityA.get('expertise', None)

            if inv:
                config.paper_invitation = inv
            if id:
                config.paper_id = id
            if excl_inv:
                config.exclusion_inv = excl_inv.get('exclusion', {}).get('invitation', None)
        elif api_request.entityB['type'] == 'Note':
            inv, id = api_request.entityB.get('invitation', None), api_request.entityB.get('id', None)
            excl_inv = api_request.entityB.get('expertise', None)

            if inv:
                config.paper_invitation = inv
            if id:
                config.paper_id = id
            if excl_inv:
                config.exclusion_inv = excl_inv.get('exclusion', {}).get('invitation', None)

        # Validate that other paper fields are none if an alternate match group is present
        if config.alternate_match_group is not None and (config.paper_id is not None or config.paper_invitation is not None):
            raise openreview.OpenReviewException('Bad request: Cannot provide paper id/invitation and alternate match group')

        # Load optional model params from default config
        path_fields = ['work_dir', 'scores_path', 'publications_path', 'submissions_path']
        allowed_model_params = [
            'name',
            'sparseValue',
            'useTitle',
            'useAbstract',
            'scoreComputation',
            'skipSpecter'
        ]
        config.model = starting_config.get('model', None)
        model_params = starting_config.get('model_params', {})
        config.model_params = {}
        config.model_params['use_title'] = model_params.get('use_title', None)
        config.model_params['use_abstract'] = model_params.get('use_abstract', None)
        config.model_params['average_score'] = model_params.get('average_score', None)
        config.model_params['max_score'] = model_params.get('max_score', None)
        config.model_params['skip_specter'] = model_params.get('skip_specter', None)
        config.model_params['batch_size'] = model_params.get('batch_size', 1)
        config.model_params['use_cuda'] = model_params.get('use_cuda', False)

        # Attempt to load any API request model params
        api_model = api_request.model
        if api_model:
            for param in api_model.keys():
                # Handle special cases
                if param == 'scoreComputation':
                    compute_with = api_model.get('scoreComputation', None)
                    if compute_with == 'max':
                        config.model_params['max_score'] = True
                        config.model_params['average_score'] = False
                    elif compute_with == 'avg':
                        config.model_params['max_score'] = False
                        config.model_params['average_score'] = True
                    else:
                        raise openreview.OpenReviewException("Bad request: invalid value in field 'scoreComputation' in 'model' object")
                    continue
                
                # Handle general case
                if param not in allowed_model_params:
                    raise openreview.OpenReviewException(f"Bad request: unexpected fields in model: {[param]}")

                snake_param = _camel_to_snake(param)
                config.model_params[snake_param] = api_model[param]
        
        # Set server-side path fields
        for field in path_fields:
            config.model_params[field] = root_dir

        if 'specter' in config.model:
            config.model_params['specter_dir'] = server_config['SPECTER_DIR']
        if 'mfr' in config.model:
            config.model_params['mfr_feature_vocab_file'] = server_config['MFR_VOCAB_DIR']
            config.model_params['mfr_checkpoint_dir'] = server_config['MFR_CHECKPOINT_DIR']

        return config
    
    def from_json(job_config):
        config = JobConfig(
            name = job_config.get('name'),
            user_id = job_config.get('user_id'),
            job_id = job_config.get('job_id'),
            baseurl = job_config.get('baseurl'),
            baseurl_v2 = job_config.get('baseurl_v2'),
            job_dir = job_config.get('job_dir'),
            cdate = job_config.get('cdate'),
            mdate = job_config.get('mdate'),
            status = job_config.get('status'),
            description = job_config.get('description'),
            match_group = job_config.get('match_group'),
            alternate_match_group=job_config.get('alternate_match_group'),
            dataset = job_config.get('dataset'),
            model = job_config.get('model'),
            exclusion_inv = job_config.get('exclusion_inv'),
            paper_invitation = job_config.get('paper_invitation'),
            paper_id = job_config.get('paper_id'),
            model_params = job_config.get('model_params')
        )
        return config
