#!/usr/bin/env bash

mkdir -p "${TOEM_MANIFEST_DIR}"
export TOEM_CP_ENDPOINT="$(yq '.[0]' secrets/ip-addresses.yaml | cut -d "/" -f 1)"

kconf use kind-capi-test
clusterctl generate cluster "${CLUSTER_NAME}" --from templates/cluster-talos-template.yaml > "${TOEM_MANIFEST_DIR}/${CLUSTER_NAME}.yaml"
cd "${TOEM_SECRETS_DIR}"

if [ ! -f talosconfig ]; then
	cmd="talosctl gen config ${CLUSTER_NAME} https://${TOEM_CP_ENDPOINT}:6443"
	echo "${cmd}"
  eval "${cmd}"
	gfind ./ -regex  '.*\(controlplane\|worker\)-.*' -delete
fi

yq -s '"spec_" + .kind + "_" + .metadata.name' "${TOEM_PROJECT_ROOT}/${TOEM_MANIFEST_DIR}/${CLUSTER_NAME}.yaml"
yq e '. | .spec.controlPlaneConfig.controlplane.configPatches[0].value.contents |= load_str("cpem/cpem.yaml")' -i "spec_TalosControlPlane_${CLUSTER_NAME}-control-plane.yml"
yq eval-all spec_* > "${CLUSTER_NAME}.yaml"
yq '... comments=""' "${CLUSTER_NAME}.yaml" > "${CLUSTER_NAME}-no-comment.yaml"
yq 'select(.kind == "TalosControlPlane") | .spec.controlPlaneConfig.controlplane.configPatches' ${CLUSTER_NAME}.yaml > controlplane-patches.yaml
yq 'select(.kind == "TalosConfigTemplate") | .spec.template.spec.configPatches' ${CLUSTER_NAME}.yaml > worker-patches.yaml

talosWorker="worker.yaml"
talosControl="controlplane.yaml"
talosctl machineconfig patch ${talosWorker} --patch @worker-patches.yaml -o worker-patched.yaml
talosctl machineconfig patch ${talosControl} --patch @controlplane-patches.yaml -o controlplane-patched.yaml
cp ${talosWorker} worker-cli.yaml
cp ${talosControl} controlplane-cli.yaml
talosWorkerCli="worker-cli.yaml"
talosControlCli="controlplane-cli.yaml"

yq e '.cluster.externalCloudProvider.enabled = true | .cluster.externalCloudProvider.manifests[0] = "https://github.com/equinix/cloud-provider-equinix-metal/releases/download/v3.6.0/deployment.yaml"' -i "${talosWorkerCli}"
yq e '.cluster.externalCloudProvider.enabled = true | .cluster.externalCloudProvider.manifests[0] = "https://github.com/equinix/cloud-provider-equinix-metal/releases/download/v3.6.0/deployment.yaml"' -i "${talosControlCli}"
yq e '.cluster.apiServer.extraArgs.cloud-provider = "external"' -i "${talosControlCli}"
yq e '.cluster.controllerManager.extraArgs.cloud-provider = "external"' -i "${talosControlCli}"
yq e '.cluster.inlineManifests[0] = {"name":"cpem-secret", "contents":load_str("cpem/cpem.yaml")}' -i "${talosControlCli}"
yq e '.cluster.network.cni.name = "custom" | .cluster.network.cni.urls[0] = "https://raw.githubusercontent.com/projectcalico/calico/v3.24.1/manifests/calico.yaml"' -i "${talosControlCli}"
yq e '.cluster.network.cni.name = "custom" | .cluster.network.cni.urls[0] = "https://raw.githubusercontent.com/projectcalico/calico/v3.24.1/manifests/calico.yaml"' -i "${talosWorkerCli}"

# shellcheck disable=SC2016
yq e '.machine.kubelet.extraArgs.cloud-provider = "external"' -i "${talosControlCli}"
# shellcheck disable=SC2016
yq e '.machine.kubelet.extraArgs.cloud-provider = "external"' -i "${talosWorkerCli}"
yq e '.machine.network.interfaces[0].interface = "eth3" | .machine.network.interfaces[0].vip.ip = env(TOEM_CP_ENDPOINT) | .machine.network.interfaces[0].vip.equinixMetal.apiToken = env(PACKET_API_KEY)' -i "${talosControlCli}"

yq '... comments=""' "${talosWorkerCli}" > "worker-no-comment.yaml"
yq '... comments=""' "${talosControlCli}" > "controlplane-no-comment.yaml"

yq e ' del(.spec.controlPlaneConfig.controlplane.configPatches) | .spec.controlPlaneConfig.controlplane.generateType = "none" | .spec.controlPlaneConfig.controlplane.data = load_str("controlplane-no-comment.yaml")' -i spec_TalosControlPlane_talos-alloy-102-control-plane.yml
yq e ' del(.spec.template.spec.configPatches) | .spec.template.spec.generateType = "none" | .spec.template.spec.data = load_str("worker-no-comment.yaml")' -i spec_TalosConfigTemplate_talos-alloy-102-worker.yml
yq eval-all spec_* > "${CLUSTER_NAME}-static-config.yaml"
yq '... comments=""' "${CLUSTER_NAME}-static-config.yaml" > "${CLUSTER_NAME}-static-config-no-comment.yaml"

rm spec_*
cd "${TOEM_PROJECT_ROOT}"

function update_hashbang_and_validate() {
	# In our case configs are useless without https://www.talos.dev/v1.3/talos-guides/install/bare-metal-platforms/equinix-metal/#passing-in-the-configuration-as-user-data
	local talos_file=$1
	local hashBang="#!talos"
	local SED_OPTIONS='1s/^/'${hashBang}'\n/'
	echo "$talos_file"
	local first_line=$(head -n 1 < ${talos_file})
	if [ "${first_line}" != "${hashBang}" ]; then
		sed -i '' "${SED_OPTIONS}" "${talos_file}"
	fi
	talosctl validate -m cloud -c "${talos_file}"
}

export -f update_hashbang_and_validate
gfind secrets -regex  '.*\(controlplane\|worker\).*' -exec bash -c "update_hashbang_and_validate {}" \;
diff <(yq -P 'sort_keys(..)' secrets/controlplane-patched.yaml) <(yq -P 'sort_keys(..)' secrets/controlplane-no-comment.yaml)
diff <(yq -P 'sort_keys(..)' secrets/worker-patched.yaml) <(yq -P 'sort_keys(..)' secrets/worker-no-comment.yaml)