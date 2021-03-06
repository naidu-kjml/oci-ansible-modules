# Copyright (c) 2017, 2019 Oracle and/or its affiliates.
# This software is made available to you under the terms of the GPL 3.0 license or the Apache 2.0 license.
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)
# Apache License v2.0
# See LICENSE.TXT for details.

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.oracle import oci_common_utils, oci_utils


try:
    import oci
    from oci.exceptions import ServiceError, MaximumWaitTimeExceeded
    from oci.util import to_dict
    from oci.core.models import (
        AddedNetworkSecurityGroupSecurityRules,
        UpdatedNetworkSecurityGroupSecurityRules,
    )
    import json

    HAS_OCI_PY_SDK = True

except ImportError:
    HAS_OCI_PY_SDK = False


class SecurityRuleActionsHelperCustom:
    def _add_network_security_group_rules_idempotency_check(self):
        existing_security_rules = self.list_security_rules()
        provided_security_rules = self.module.params.get("security_rules", [])
        provided_security_rules_to_add = []

        existing_security_rules_as_dicts = [
            to_dict(security_rule) for security_rule in existing_security_rules
        ]

        for provided_security_rule in provided_security_rules:
            if not oci_common_utils.is_in_list(
                existing_security_rules_as_dicts, element=provided_security_rule
            ):
                provided_security_rules_to_add.append(provided_security_rule)

        if len(provided_security_rules_to_add) == 0:
            resource = AddedNetworkSecurityGroupSecurityRules(
                security_rules=self.list_security_rules()
            )
            return oci_common_utils.get_result(
                changed=False,
                resource_type=self.resource_type,
                resource=to_dict(resource),
            )
        else:
            self.module.params["security_rules"] = provided_security_rules_to_add

    def _update_network_security_group_rules_idempotency_check(self):
        existing_security_rules = self.list_security_rules()
        provided_security_rules = self.module.params.get("security_rules", [])

        existing_security_rules_as_dicts = [
            to_dict(security_rule) for security_rule in existing_security_rules
        ]

        all_rules_to_update_already_exist_and_match = True
        for provided_security_rule in provided_security_rules:
            if not oci_common_utils.is_in_list(
                existing_security_rules_as_dicts, element=provided_security_rule
            ):
                all_rules_to_update_already_exist_and_match = False

        if all_rules_to_update_already_exist_and_match:
            resource = UpdatedNetworkSecurityGroupSecurityRules(
                security_rules=self.list_security_rules()
            )
            return oci_common_utils.get_result(
                changed=False,
                resource_type=self.resource_type,
                resource=to_dict(resource),
            )

    def _remove_network_security_group_rules_idempotency_check(self):
        existing_security_rules = self.list_security_rules()
        provided_security_rule_ids_to_delete = self.module.params.get(
            "security_rule_ids", []
        )
        security_rule_ids_to_delete = []
        for existing_security_rule in existing_security_rules:
            if existing_security_rule.id in provided_security_rule_ids_to_delete:
                security_rule_ids_to_delete.append(existing_security_rule.id)

        if len(security_rule_ids_to_delete) == 0:
            # RemoveNetworkSecurityGroupSecurityRules returns nothing, but in order to keep return type consistent
            # across add / remove / delete, we choose to return UpdatedNetworkSecurityGroupSecurityRules with an
            # empty 'security_rules' list
            resource = UpdatedNetworkSecurityGroupSecurityRules(
                security_rules=self.list_security_rules()
            )
            return oci_common_utils.get_result(
                changed=False,
                resource_type=self.resource_type,
                resource=to_dict(resource),
            )
        else:
            self.module.params["security_rule_ids"] = security_rule_ids_to_delete

    def perform_action(self, action):

        action_fn = self.get_action_fn(action)
        if not action_fn:
            self.module.fail_json(msg="{0} not supported by the module.".format(action))

        # the idempotency checks for these actions are custom since we aren't doing the regular
        # check for existence, we are checking if a requested resource is present within a list
        if action == "add_network_security_group_security_rules":
            action_idempotency_checks_fn = (
                self._add_network_security_group_rules_idempotency_check
            )
            check_mode_response_resource = to_dict(
                AddedNetworkSecurityGroupSecurityRules(security_rules=[])
            )
        elif action == "update_network_security_group_security_rules":
            action_idempotency_checks_fn = (
                self._update_network_security_group_rules_idempotency_check
            )
            check_mode_response_resource = to_dict(
                UpdatedNetworkSecurityGroupSecurityRules(security_rules=[])
            )
        elif action == "remove_network_security_group_security_rules":
            action_idempotency_checks_fn = (
                self._remove_network_security_group_rules_idempotency_check
            )
            # RemoveNetworkSecurityGroupSecurityRules returns nothing, but in order to keep return type consistent
            # across add / remove / delete, we choose to return UpdatedNetworkSecurityGroupSecurityRules with an
            # empty 'security_rules' list
            check_mode_response_resource = to_dict(
                UpdatedNetworkSecurityGroupSecurityRules(security_rules=[])
            )
        else:
            self.module.fail_json(
                msg="Performing action failed for unrecognized action: {0}".format(
                    action
                )
            )

        result = action_idempotency_checks_fn()
        if result:
            return result

        if self.check_mode:
            return oci_common_utils.get_result(
                changed=True,
                resource_type=self.resource_type,
                resource=check_mode_response_resource,
            )

        try:
            actioned_resource = action_fn()
        except MaximumWaitTimeExceeded as mwtex:
            self.module.fail_json(msg=str(mwtex))
        except ServiceError as se:
            self.module.fail_json(
                msg="Performing action failed with exception: {0}".format(se.message)
            )
        else:
            # - the individual action operations return the rules that were acted on (except REMOVE which returns nothing)
            #   to keep consistent with patterns in other modules, we override here to return the current set of all rules
            # - in order to return the same format as the generated docs for actions operations (result.security_rule.security_rules)
            #    we use AddedNetworkSecurityGroupSecurityRules here as a wrapper
            resource = AddedNetworkSecurityGroupSecurityRules(
                security_rules=self.list_security_rules()
            )
            return oci_common_utils.get_result(
                changed=True,
                resource_type=self.resource_type,
                resource=to_dict(resource),
            )

    def list_security_rules(self):
        optional_list_method_params = ["direction", "sort_by", "sort_order"]
        optional_kwargs = dict(
            (param, self.module.params[param])
            for param in optional_list_method_params
            if self.module.params.get(param) is not None
        )
        return oci_common_utils.list_all_resources(
            self.client.list_network_security_group_security_rules,
            network_security_group_id=self.module.params.get(
                "network_security_group_id"
            ),
            **optional_kwargs
        )
