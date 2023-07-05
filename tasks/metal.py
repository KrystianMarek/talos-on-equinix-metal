import json
import os

import yaml
from invoke import task

from tasks.controllers.MetalCtrl import MetalCtrl
from tasks.dao.LocalState import LocalState
from tasks.helpers import str_presenter, get_secrets_dir, \
    get_cpem_config, get_constellation

yaml.add_representer(str, str_presenter)
yaml.representer.SafeRepresenter.add_representer(str, str_presenter)  # to use with safe_dump


@task()
def generate_cpem_config(ctx, cpem_config_file_name="cpem/cpem.yaml"):
    """
    Produces [secrets_dir]/cpem/cpem.yaml - 'Cloud Provider for Equinix Metal' config spec
    """
    cpem_config = get_cpem_config()
    ctx.run("mkdir -p {}".format(
        os.path.join(
            get_secrets_dir(),
            'cpem'
        )
    ), echo=True)

    command = "kubectl create -o yaml \
    --dry-run='client' secret generic -n kube-system metal-cloud-config \
    --from-literal='cloud-sa.json={}'"

    print(command.format('[REDACTED]'))
    k8s_secret = ctx.run(command.format(
        json.dumps(cpem_config)
    ), hide='stdout', echo=False)

    yaml_k8s_secret = yaml.safe_load(k8s_secret.stdout)
    del yaml_k8s_secret['metadata']['creationTimestamp']

    with open(os.path.join(get_secrets_dir(), cpem_config_file_name), 'w') as cpem_config_file:
        yaml.dump(yaml_k8s_secret, cpem_config_file)


# @task()
# def create_config_dirs(ctx):
#     """
#     Produces [secrets_dir]/[cluster_name...] config directories based of spec defined in invoke.yaml
#     """
#     cluster_spec = get_constellation_clusters()
#     for cluster in cluster_spec:
#         ctx.run("mkdir -p {}".format(os.path.join(
#             get_secrets_dir(),
#             cluster.name
#         )), echo=True)


# def render_vip_addresses_file(cluster: Cluster):
#     data = {
#         VipRole.cp: ReservedVIPs(),
#         VipRole.mesh: ReservedVIPs(),
#         VipRole.ingress: ReservedVIPs()
#     }
#
#     for vip in cluster.vips:
#         data[vip.role].extend(vip.reserved)
#
#         with open(get_ip_addresses_file_path(cluster, vip.role), 'w') as ip_addresses_file:
#             ip_addresses_file.write(data[vip.role].yaml())


# def register_global_vip(ctx, vip: Vip, tags: list):
#     """
#     We want to ensure that only one global_ipv4 is registered for all satellites. Following behaviour should not
#     affect the management cluster (bary).
#
#     ToDo:
#         There is a bug in Metal CLI that prevents us from using the CLI in this case.
#         Thankfully API endpoint works.
#         https://deploy.equinix.com/developers/docs/metal/networking/global-anycast-ips/
#     """
#     payload = {
#         "type": VipType.global_ipv4,
#         "quantity": vip.count,
#         "fail_on_approval_required": "true",
#         "tags": tags
#     }
#     result = ctx.run("curl -s -X POST "
#                      "-H 'Content-Type: application/json' "
#                      "-H \"X-Auth-Token: {}\" "
#                      "\"https://api.equinix.com/metal/v1/projects/{}/ips\" "
#                      "-d '{}'".format(
#                             "${METAL_AUTH_TOKEN}",
#                             "${METAL_PROJECT_ID}",
#                             json.dumps(payload)
#                         ), hide='stdout', echo=True).stdout
#
#     if vip.count > 1:
#         return [dict(yaml.safe_load(result))]
#     else:
#         return list(yaml.safe_load_all(result))


# def get_vip_tags(address_role: VipRole, cluster: Cluster) -> list:
#     """
#     ToDo: Despite all the efforts to disable it
#         https://github.com/kubernetes-sigs/cluster-api-provider-packet on its own registers a VIP for the control plane.
#         We need one so we will use it. The tag remains defined by CAPP.
#         As for the tags the 'cp' VIP is used for the Control Plane. The 'ingress' VIP will be used by the ingress.
#         The 'mesh' VIP will be used by cilium as ClusterMesh endpoint.
#     """
#     if address_role == VipRole.cp:
#         return ["cluster-api-provider-packet:cluster-id:{}".format(cluster.name)]
#     else:
#         return ["gocy:cluster:{}".format(cluster.name), "gocy:vip:{}".format(address_role.name)]
#
#
# def is_constellation_member(tags: list) -> bool:
#     cluster_name_from_tag = tags[0].split(":")[-1:][0]  # First tag, last field, delimited by :
#     if type(cluster_name_from_tag) is not str:
#         print("Tags: {} are not what was expected".format(tags))
#
#     clusters = get_constellation_clusters()
#     for cluster in clusters:
#         if cluster.name == cluster_name_from_tag:
#             return True
#
#     return False


# def vip_role_match(vip_role: VipRole, tags: list) -> bool:
#     if len(tags) == 1:
#         if vip_role == VipRole.cp:
#             return True
#     elif len(tags) > 1:
#         role_from_tag = tags[1].split(":")[-1:][0]  # Second tag, last field, delimited by :
#         if role_from_tag == vip_role:
#             return True
#
#     return False
#
#
# def register_public_vip(ctx, vip: Vip, cluster: Cluster, tags: list):
#     result = ctx.run("metal ip request --type {} --quantity {} --metro {} --tags '{}' -o yaml".format(
#         VipType.public_ipv4,
#         vip.count,
#         cluster.metro,
#         ",".join(tags)
#     ), hide='stdout', echo=True).stdout
#     if vip.count > 1:
#         return [dict(yaml.safe_load(result))]
#     else:
#         return list(yaml.safe_load_all(result))


# @task(create_config_dirs)
@task()
def register_vips(ctx, project_vips_file_name='project-ips.yaml'):
    """
    Registers VIPs as per constellation spec in ~/.gocy/[constellation_name].constellation.yaml
    """
    state = LocalState()
    metal_ctrl = MetalCtrl(state.constellation, True)
    metal_ctrl.register_vips(ctx)


@task()
def list_facilities(ctx):
    """
    Wrapper for 'metal facilities get'
    """
    ctx.run('metal facilities get', echo=True)


@task()
def check_capacity(ctx):
    """
    Check device capacity for clusters specified in invoke.yaml
    """
    nodes_total = dict()
    constellation = get_constellation()
    bary_metro = constellation.bary.metro
    nodes_total[bary_metro] = dict()
    bary_nodes = constellation.bary.control_nodes
    bary_nodes.extend(constellation.bary.worker_nodes)

    for node in bary_nodes:
        if node.plan not in nodes_total[bary_metro]:
            nodes_total[bary_metro][node.plan] = node.count
        else:
            nodes_total[bary_metro][node.plan] = nodes_total[bary_metro][node.plan] + node.count

    for satellite in constellation.satellites:
        if satellite.metro not in nodes_total:
            nodes_total[satellite.metro] = dict()

        satellite_nodes = satellite.worker_nodes
        satellite_nodes.extend(satellite.control_nodes)
        for node in satellite_nodes:
            if node.plan not in nodes_total[satellite.metro]:
                nodes_total[satellite.metro][node.plan] = node.count
            else:
                nodes_total[satellite.metro][node.plan] = nodes_total[satellite.metro][node.plan] + node.count

    for metro in nodes_total:
        for node_type, count in nodes_total[metro].items():
            ctx.run("metal capacity check --metros {} --plans {} --quantity {}".format(
                metro, node_type, count
            ), echo=True)
