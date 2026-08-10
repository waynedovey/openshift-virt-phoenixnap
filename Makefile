SHELL := /bin/bash
INVENTORY := inventories/lab/hosts.yml
VENV := .venv
PYTHON ?= python3
ANSIBLE_PLAYBOOK := $(VENV)/bin/ansible-playbook
ANSIBLE_GALAXY := $(VENV)/bin/ansible-galaxy
ANSIBLE_LINT := $(VENV)/bin/ansible-lint

.PHONY: bootstrap validate availability preflight prepare-hub private-networks bgp replace-servers provision dns install virt nmstate vm-l2 evpn status deploy destroy lint clean-venv

$(ANSIBLE_PLAYBOOK): requirements.txt requirements.yml
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/python -m pip install --upgrade pip
	$(VENV)/bin/python -m pip install -r requirements.txt
	$(ANSIBLE_GALAXY) collection install -r requirements.yml

bootstrap: $(ANSIBLE_PLAYBOOK)
	@echo "Ansible environment ready: $$($(ANSIBLE_PLAYBOOK) --version | head -1)"
	@echo "Python: $$($(VENV)/bin/python -c 'import sys; print(sys.executable)')"
	@$(VENV)/bin/python -c 'import kubernetes; print("Kubernetes Python client:", kubernetes.__version__)'

validate: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/00_validate.yml

availability: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/00a_availability.yml

preflight: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/01_preflight.yml

prepare-hub: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/02_prepare_rhacm.yml

private-networks: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/03a_private_networks.yml

bgp: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/03_phoenixnap_bgp.yml

replace-servers: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/04_replace_servers.yml -e confirm_replace=true

provision: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/04_provision_servers.yml

dns: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/05_cloudflare_dns.yml

install: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/06_wait_and_export.yml

virt: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/07_virtualization.yml

nmstate: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/07b_nmstate.yml

vm-l2: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/07c_vm_localnet.yml

evpn: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/08_evpn.yml

status: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) playbooks/09_status.yml

deploy: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) site.yml

destroy: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_PLAYBOOK) -i $(INVENTORY) destroy.yml -e confirm_destroy=true

lint: $(ANSIBLE_PLAYBOOK)
	$(ANSIBLE_LINT) site.yml destroy.yml playbooks/*.yml

clean-venv:
	rm -rf $(VENV)
