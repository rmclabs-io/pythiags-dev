from _typeshed import Incomplete

class KafkaAdminClient:
    DEFAULT_CONFIG: Incomplete
    config: Incomplete
    _metrics: Incomplete
    _client: Incomplete
    _closed: bool
    def __init__(self, **configs) -> None: ...
    def close(self) -> None: ...
    def _matching_api_version(self, operation): ...
    def _validate_timeout(self, timeout_ms): ...
    _controller_id: Incomplete
    def _refresh_controller_id(self) -> None: ...
    def _find_coordinator_id_send_request(self, group_id): ...
    def _find_coordinator_id_process_response(self, response): ...
    def _find_coordinator_ids(self, group_ids): ...
    def _send_request_to_node(self, node_id, request): ...
    def _send_request_to_controller(self, request): ...
    @staticmethod
    def _convert_new_topic_request(new_topic): ...
    def create_topics(self, new_topics, timeout_ms: Incomplete | None = ..., validate_only: bool = ...): ...
    def delete_topics(self, topics, timeout_ms: Incomplete | None = ...): ...
    def _get_cluster_metadata(self, topics: Incomplete | None = ..., auto_topic_creation: bool = ...): ...
    def list_topics(self): ...
    def describe_topics(self, topics: Incomplete | None = ...): ...
    def describe_cluster(self): ...
    @staticmethod
    def _convert_describe_acls_response_to_acls(describe_response): ...
    def describe_acls(self, acl_filter): ...
    @staticmethod
    def _convert_create_acls_resource_request_v0(acl): ...
    @staticmethod
    def _convert_create_acls_resource_request_v1(acl): ...
    @staticmethod
    def _convert_create_acls_response_to_acls(acls, create_response): ...
    def create_acls(self, acls): ...
    @staticmethod
    def _convert_delete_acls_resource_request_v0(acl): ...
    @staticmethod
    def _convert_delete_acls_resource_request_v1(acl): ...
    @staticmethod
    def _convert_delete_acls_response_to_matching_acls(acl_filters, delete_response): ...
    def delete_acls(self, acl_filters): ...
    @staticmethod
    def _convert_describe_config_resource_request(config_resource): ...
    def describe_configs(self, config_resources, include_synonyms: bool = ...): ...
    @staticmethod
    def _convert_alter_config_resource_request(config_resource): ...
    def alter_configs(self, config_resources): ...
    @staticmethod
    def _convert_create_partitions_request(topic_name, new_partitions): ...
    def create_partitions(self, topic_partitions, timeout_ms: Incomplete | None = ..., validate_only: bool = ...): ...
    def _describe_consumer_groups_send_request(self, group_id, group_coordinator_id, include_authorized_operations: bool = ...): ...
    def _describe_consumer_groups_process_response(self, response): ...
    def describe_consumer_groups(self, group_ids, group_coordinator_id: Incomplete | None = ..., include_authorized_operations: bool = ...): ...
    def _list_consumer_groups_send_request(self, broker_id): ...
    def _list_consumer_groups_process_response(self, response): ...
    def list_consumer_groups(self, broker_ids: Incomplete | None = ...): ...
    def _list_consumer_group_offsets_send_request(self, group_id, group_coordinator_id, partitions: Incomplete | None = ...): ...
    def _list_consumer_group_offsets_process_response(self, response): ...
    def list_consumer_group_offsets(self, group_id, group_coordinator_id: Incomplete | None = ..., partitions: Incomplete | None = ...): ...
    def delete_consumer_groups(self, group_ids, group_coordinator_id: Incomplete | None = ...): ...
    def _convert_delete_groups_response(self, response): ...
    def _delete_consumer_groups_send_request(self, group_ids, group_coordinator_id): ...
    def _wait_for_futures(self, futures) -> None: ...




class NewTopic:
    name: Incomplete
    num_partitions: Incomplete
    replication_factor: Incomplete
    replica_assignments: Incomplete
    topic_configs: Incomplete
    def __init__(self, name, num_partitions, replication_factor, replica_assignments: Incomplete | None = ..., topic_configs: Incomplete | None = ...) -> None: ...