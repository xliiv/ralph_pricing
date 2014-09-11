# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime
import mock

from django.test import TestCase
from django.test.utils import override_settings

from ralph_scrooge.models import PricingObjectType
from ralph_scrooge.plugins.collect.tenant import (
    get_tenant_service_environment,
    get_tenant_unknown_service_environment,
    InvalidTenantServiceEnvironment,
    save_tenant_info,
    save_daily_tenant_info,
    tenant as tenant_plugin,
    UnknownServiceEnvironmentNotConfigured,
)
from ralph_scrooge.tests.utils.factory import (
    EnvironmentFactory,
    ServiceFactory,
    ServiceEnvironmentFactory,
    TenantInfoFactory,
)


TEST_SETTINGS_SITES = dict(
    OPENSTACK_SITES=[
        {
            'OS_METERING_URL': "http://127.0.0.1:8777",
            'OS_TENANT_NAME': 'testtenant',
            'OS_USERNAME': 'testuser',
            'OS_PASSWORD': 'supersecretpass',
            'OS_AUTH_URL': "http://127.0.0.1:5000/v2.0",
            'CEILOMETER_CONNECTION': "mysql://foo:bar@example.com:3306",
            'WAREHOUSE': 'WH1',
        },
        {
            'OS_METERING_URL': "http://127.0.0.2:8777",
            'OS_TENANT_NAME': 'testtenant2',
            'OS_USERNAME': 'testuser2',
            'OS_PASSWORD': 'supersecretpass2',
            'OS_AUTH_URL': "http://127.0.0.2:5000/v2.0",
            'CEILOMETER_CONNECTION': "mysql://foo:bar@example.com:3307",
            'WAREHOUSE': 'WH2',
        },
    ],
)
UNKNOWN_SERVICE_ENVIRONMENT = ('os-1', 'env1')
SERVICE_FIELD = 'tenant_service'
ENVIRONMENT_FIELD = 'tenant_environment'
TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS = dict(
    UNKNOWN_SERVICES_ENVIRONMENTS={
        'tenant': UNKNOWN_SERVICE_ENVIRONMENT,
    }
)
TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD = dict(
    OPENSTACK_TENANT_SERVICE_FIELD=SERVICE_FIELD,
    OPENSTACK_TENANT_ENVIRONMENT_FIELD=ENVIRONMENT_FIELD,
)


def join_settings(*args):
    return reduce(lambda a, d: a.update(d) or a, args, {})

TEST_SETTINGS_ALL = join_settings(
    TEST_SETTINGS_SITES,
    TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD,
    TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS,
)


class TestServiceCollectPlugin(TestCase):
    def setUp(self):
        self.service_environment = ServiceEnvironmentFactory()
        self.unknown_service_environment = ServiceEnvironmentFactory()
        self.today = datetime.date(2014, 7, 1)

    def _get_sample_tenant(self):
        """
        Sample tenant from keystoneclient
        """
        return mock.Mock(
            id='12345qwerty',
            description='qwerty;asdfg;',
            name='sample_tenant',
            enabled=True,
        )

    def _compare_tenants(self, sample_tenant, tenant_info):
        self.assertEquals(tenant_info.tenant_id, sample_tenant.id)
        self.assertEquals(tenant_info.name, sample_tenant.name)
        self.assertEquals(tenant_info.remarks, sample_tenant.description)
        self.assertEquals(tenant_info.type, PricingObjectType.tenant)

    @override_settings(**TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD)
    def test_get_tenant_service_environment(self):
        tenant = self._get_sample_tenant()
        service_environment = ServiceEnvironmentFactory()
        setattr(
            tenant,
            SERVICE_FIELD,
            service_environment.service.name  # TODO: change to symbol
        )
        setattr(
            tenant,
            ENVIRONMENT_FIELD,
            service_environment.environment.name  # TODO: change to symbol
        )
        self.assertEquals(
            service_environment,
            get_tenant_service_environment(tenant)
        )

    @override_settings(**TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD)
    def test_get_tenant_service_environment_invalid_service(self):
        tenant = self._get_sample_tenant()
        service = ServiceFactory()
        service_environment = ServiceEnvironmentFactory.build(service=service)
        setattr(
            tenant,
            SERVICE_FIELD,
            service_environment.service.name  # TODO: change to symbol
        )
        setattr(
            tenant,
            ENVIRONMENT_FIELD,
            service_environment.environment.name
        )
        with self.assertRaises(InvalidTenantServiceEnvironment):
            get_tenant_service_environment(tenant)

    @override_settings(**TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD)
    def test_get_tenant_service_environment_without_service_field(self):
        tenant = self._get_sample_tenant()
        service_environment = ServiceEnvironmentFactory.build()
        setattr(
            tenant,
            SERVICE_FIELD,
            None,
        )
        setattr(
            tenant,
            ENVIRONMENT_FIELD,
            service_environment.environment.name
        )
        with self.assertRaises(InvalidTenantServiceEnvironment):
            get_tenant_service_environment(tenant)

    @override_settings(**TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD)
    def test_get_tenant_service_environment_invalid_environment(self):
        tenant = self._get_sample_tenant()
        environment = EnvironmentFactory()
        service_environment = ServiceEnvironmentFactory.build(
            environment=environment
        )
        setattr(
            tenant,
            SERVICE_FIELD,
            service_environment.service.name  # TODO: change to symbol
        )
        setattr(
            tenant,
            ENVIRONMENT_FIELD,
            service_environment.environment.name
        )
        with self.assertRaises(InvalidTenantServiceEnvironment):
            get_tenant_service_environment(tenant)

    @override_settings(**TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD)
    def test_get_tenant_service_environment_without_environment_field(self):
        tenant = self._get_sample_tenant()
        service_environment = ServiceEnvironmentFactory.build()
        setattr(
            tenant,
            SERVICE_FIELD,
            service_environment.service.name,  # TODO: change to symbol
        )
        setattr(
            tenant,
            ENVIRONMENT_FIELD,
            None
        )
        with self.assertRaises(InvalidTenantServiceEnvironment):
            get_tenant_service_environment(tenant)

    @mock.patch('ralph_scrooge.plugins.collect.tenant.get_tenant_service_environment')  # noqa
    def test_save_tenant_info(
        self,
        get_tenant_service_environment_mock,
    ):
        get_tenant_service_environment_mock.return_value = (
            self.service_environment
        )
        sample_tenant = self._get_sample_tenant()
        created, tenant_info = save_tenant_info(
            sample_tenant,
            self.unknown_service_environment
        )
        self.assertTrue(created)
        self._compare_tenants(sample_tenant, tenant_info)
        self.assertEquals(
            tenant_info.service_environment,
            self.service_environment
        )

    @mock.patch('ralph_scrooge.plugins.collect.tenant.get_tenant_service_environment')  # noqa
    def test_save_tenant_info_invalid_service_environment(
        self,
        get_tenant_service_environment_mock,
    ):
        get_tenant_service_environment_mock.side_effect = (
            InvalidTenantServiceEnvironment()
        )
        sample_tenant = self._get_sample_tenant()
        created, tenant_info = save_tenant_info(
            sample_tenant,
            self.unknown_service_environment
        )
        self.assertTrue(created)
        self._compare_tenants(sample_tenant, tenant_info)
        self.assertEquals(
            tenant_info.service_environment,
            self.unknown_service_environment
        )

    def test_save_daily_tenant_info(self):
        tenant_info = TenantInfoFactory()
        sample_tenant = self._get_sample_tenant()
        result = save_daily_tenant_info(
            sample_tenant,
            tenant_info,
            self.today
        )
        self.assertEquals(result.tenant_info, tenant_info)
        self.assertEquals(result.pricing_object, tenant_info)
        self.assertEquals(result.date, self.today)
        self.assertEquals(
            result.service_environment,
            tenant_info.service_environment
        )
        self.assertEquals(result.enabled, sample_tenant.enabled)

    @override_settings(**TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS)
    def test_get_tenant_unknown_service_environment(self):
        service_environment = ServiceEnvironmentFactory(
            service__ci_uid=UNKNOWN_SERVICE_ENVIRONMENT[0],
            environment__name=UNKNOWN_SERVICE_ENVIRONMENT[1],
        )
        self.assertEquals(
            service_environment,
            get_tenant_unknown_service_environment()
        )

    @override_settings(**TEST_SETTINGS_UNKNOWN_SERVICES_ENVIRONMENTS)
    def test_get_tenant_unknown_service_invalid_config(self):
        ServiceEnvironmentFactory()
        with self.assertRaises(UnknownServiceEnvironmentNotConfigured):
            get_tenant_unknown_service_environment()

    def test_get_tenant_unknown_service_not_configured(self):
        with self.assertRaises(UnknownServiceEnvironmentNotConfigured):
            get_tenant_unknown_service_environment()

    @mock.patch('ralph_scrooge.plugins.collect.tenant.get_tenants_list')
    @mock.patch('ralph_scrooge.plugins.collect.tenant.update_tenant')
    @override_settings(**TEST_SETTINGS_ALL)
    def test_tenant_plugin(self, update_tenant_mock, get_tenants_list_mock):
        unknown_service_environment = ServiceEnvironmentFactory(
            service__ci_uid=UNKNOWN_SERVICE_ENVIRONMENT[0],
            environment__name=UNKNOWN_SERVICE_ENVIRONMENT[1],
        )
        update_tenant_mock.return_value = True
        tenants_list = [self._get_sample_tenant()] * 5
        get_tenants_list_mock.return_value = tenants_list
        result = tenant_plugin(self.today)
        self.assertEquals(
            result,
            (True, 'Tenants: 10 new, 0 updated, 10 total')
        )
        self.assertEquals(get_tenants_list_mock.call_count, 2)
        self.assertEquals(update_tenant_mock.call_count, 10)
        update_tenant_mock.assert_any_call(
            tenants_list[0],
            self.today,
            unknown_service_environment,
        )
        for site in TEST_SETTINGS_SITES['OPENSTACK_SITES']:
            get_tenants_list_mock.assert_any_call(site)

    @mock.patch('ralph_scrooge.plugins.collect.tenant.get_tenant_unknown_service_environment')  # noqa
    @override_settings(**TEST_SETTINGS_SERVICE_ENVIRONMENT_FIELD)
    def test_tenant_plugin_unknown_service_not_configured(
        self,
        get_tenant_unknown_service_environment_mock
    ):
        get_tenant_unknown_service_environment_mock.side_effect = (
            UnknownServiceEnvironmentNotConfigured()
        )
        result = tenant_plugin(self.today)
        self.assertEquals(
            result,
            (
                False,
                'Unknown service environment not configured for tenant plugin'
            )
        )

    def test_tenant_plugin_service_field_not_configured(self):
        result = tenant_plugin(self.today)
        self.assertEquals(
            result,
            (False, 'Tenant service field not configured')
        )

    @override_settings(OPENSTACK_TENANT_SERVICE_FIELD='f1')
    def test_tenant_plugin_service_environment_not_configured(self):
        result = tenant_plugin(self.today)
        self.assertEquals(
            result,
            (False, 'Tenant environment field not configured')
        )