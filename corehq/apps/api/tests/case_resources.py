import json
import uuid
from datetime import datetime

from django.utils.http import urlencode

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from dimagi.utils.parsing import json_format_datetime

from corehq.apps.api.resources import v0_3, v0_4
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import WebUser
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.pillows.case import transform_case_for_elasticsearch
from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
from corehq.util.elastic import reset_es_index
from pillowtop.es_utils import initialize_index_and_mapping

from .utils import APIResourceTest, FakeFormESView


class TestCommCareCaseResource(APIResourceTest):
    resource = v0_4.CommCareCaseResource

    def setUp(self):
        self.es = get_es_new()
        reset_es_index(CASE_INDEX_INFO)
        initialize_index_and_mapping(self.es, CASE_INDEX_INFO)

    def _setup_case(self):

        modify_date = datetime.utcnow()

        backend_case = CommCareCase(server_modified_on=modify_date, domain=self.domain.name)
        backend_case.save()
        self.addCleanup(backend_case.delete)

        translated_doc = transform_case_for_elasticsearch(backend_case.to_json())

        send_to_elasticsearch('cases', translated_doc)
        self.es.indices.refresh(CASE_INDEX_INFO.index)
        return backend_case

    def test_get_list(self):
        """
        Any case in the appropriate domain should be in the list from the API.
        """
        backend_case = self._setup_case()
        response = self._assert_auth_get_resource(self.list_endpoint)
        self.assertEqual(response.status_code, 200)

        api_cases = json.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 1)

        api_case = api_cases[0]
        self.assertEqual(api_case['server_date_modified'], json_format_datetime(backend_case.server_modified_on))

    def test_get_list_format(self):
        """
        Any case in the appropriate domain should be in the list from the API.
        """
        backend_case = self._setup_case()

        # Get XML response
        response = self._assert_auth_get_resource(self.list_endpoint, headers={'HTTP_ACCEPT': 'application/xml'})
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().split('\n', 1)[0]
        self.assertEqual(content, "<?xml version='1.0' encoding='utf-8'?>")

        # Force JSON response with `format=json` parameter
        response = self._assert_auth_get_resource(
            self.list_endpoint + '?format=json',
            headers={'HTTP_ACCEPT': 'application/xml'}
        )
        self.assertEqual(response.status_code, 200)

        # we should still get the same case even with the `format` param
        # https://dimagi-dev.atlassian.net/browse/HI-656
        api_cases = json.loads(response.content)['objects']
        self.assertEqual(len(api_cases), 1)

        api_case = api_cases[0]
        self.assertEqual(api_case['server_date_modified'], json_format_datetime(backend_case.server_modified_on))

    @run_with_all_backends
    def test_parent_and_child_cases(self):
        # Create cases
        parent_case_id = uuid.uuid4().hex
        parent_type = 'parent_case_type'
        parent_case = submit_case_blocks(
            CaseBlock.deprecated_init(
                case_id=parent_case_id,
                create=True,
                case_type=parent_type,
            ).as_text(),
            self.domain.name
        )[1][0]
        child_case_id = uuid.uuid4().hex
        child_case = submit_case_blocks(
            CaseBlock.deprecated_init(
                case_id=child_case_id,
                create=True,
                index={'parent': (parent_type, parent_case_id)}
            ).as_text(),
            self.domain.name
        )[1][0]

        self.addCleanup(child_case.delete)
        self.addCleanup(parent_case.delete)
        send_to_elasticsearch('cases', transform_case_for_elasticsearch(parent_case.to_json()))
        send_to_elasticsearch('cases', transform_case_for_elasticsearch(child_case.to_json()))
        self.es.indices.refresh(CASE_INDEX_INFO.index)

        # Fetch the child case through the API

        response = self._assert_auth_get_resource(self.single_endpoint(child_case_id) + "?parent_cases__full=true")
        self.assertEqual(
            response.status_code,
            200,
            "Status code was not 200. Response content was {}".format(response.content)
        )
        parent_cases = list(json.loads(response.content)['parent_cases'].values())

        # Confirm that the case appears in the resource
        self.assertEqual(len(parent_cases), 1)
        self.assertEqual(parent_cases[0]['id'], parent_case_id)

        # Fetch the parent case through the API

        response = self._assert_auth_get_resource(self.single_endpoint(parent_case_id) + "?child_cases__full=true")
        self.assertEqual(
            response.status_code,
            200,
            "Status code was not 200. Response content was {}".format(response.content)
        )
        child_cases = list(json.loads(response.content)['child_cases'].values())

        # Confirm that the case appears in the resource
        self.assertEqual(len(child_cases), 1)
        self.assertEqual(child_cases[0]['id'], child_case_id)


class TestCommCareCaseResourceQueries(APIResourceTest):
    """
    Tests the CommCareCaseREsource, currently only v0_4
    """
    resource = v0_4.CommCareCaseResource

    def _test_es_query(self, url_params, expected_query, fake_es=None):
        fake_es = fake_es or FakeFormESView()
        v0_3.MOCK_CASE_ES_VIEW = fake_es

        response = self._assert_auth_get_resource('%s?%s' % (self.list_endpoint, urlencode(url_params)))
        self.assertEqual(response.status_code, 200)
        self.assertItemsEqual(fake_es.queries[0]['filter']['and'], expected_query)

    def test_get_list_legacy_filters(self):
        expected = [
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'type': 'movie'}},
            {'term': {'name': 'lethal weapon ii'}},
        ]
        params = {
            'case_type': 'Movie',
            'case_name': 'Lethal Weapon II',
        }
        self._test_es_query(params, expected)

    def test_get_list_case_sensitivity(self):
        expected = [
            {'term': {'domain.exact': 'qwerty'}},
            {'term': {'type': 'fish'}},
            {'term': {'type.exact': 'FISH'}},
            {'term': {'name': 'nemo'}},
            {'term': {'name.exact': 'Nemo'}},
            {'term': {'external_id': 'clownfish_1'}},
            {'term': {'external_id.exact': 'ClownFish_1'}},
        ]
        params = {
            'type': 'fish',
            'type.exact': 'FISH',
            'name': 'Nemo',
            'name.exact': 'Nemo',
            'external_id': 'ClownFish_1',
            'external_id.exact': 'ClownFish_1',
        }
        self._test_es_query(params, expected)

    def test_get_list_date_filter(self):
        start_date = datetime(1969, 6, 14)
        end_date = datetime(2011, 1, 2)
        expected = [
            {'term': {'domain.exact': 'qwerty'}},
            {'range': {'server_modified_on': {'gte': start_date.isoformat(), 'lte': end_date.isoformat()}}},
            {'range': {'modified_on': {'gte': start_date.isoformat(), 'lte': end_date.isoformat()}}},
        ]
        params = {
            'server_date_modified_end': end_date.isoformat(),
            'server_date_modified_start': start_date.isoformat(),
            'date_modified_start': start_date.isoformat(),
            'date_modified_end': end_date.isoformat(),
        }
        self._test_es_query(params, expected)

    def test_no_subscription(self):
        """
        Tests authorization function properly blocks domains without proper subscription
        :return:
        """
        community_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(community_domain.name, 'test', 'testpass', None, None)
        new_user.save()

        self.addCleanup(community_domain.delete)

        response = self._assert_auth_get_resource(self.list_endpoint, username='test', password='testpass')
        self.assertEqual(response.status_code, 403)

    def test_superuser(self):
        """
        Tests superuser overrides authorization
        :return:
        """
        community_domain = Domain.get_or_create_with_name('dvorak', is_active=True)
        new_user = WebUser.create(community_domain.name, 'test', 'testpass', None, None, is_superuser=True)
        new_user.save()

        self.addCleanup(community_domain.delete)

        response = self._assert_auth_get_resource(self.list_endpoint, username='test', password='testpass')
        self.assertEqual(response.status_code, 200)
