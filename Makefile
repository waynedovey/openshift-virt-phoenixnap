SHELL := /bin/bash
INVENTORY := inventories/lab/hosts.yml

.PHONY: bootstrap validate preflight prepare-hub bgp provision dns install virt evpn status deploy destroy lint

bootstrap:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/ansible-galaxy collection install -r requirements.yml

validate:
	ansible-playbook -i $(INVENTORY) playbooks/00_validate.yml

preflight:
	ansible-playbook -i $(INVENTORY) playbooks/01_preflight.yml

prepare-hub:
	ansible-playbook -i $(INVENTORY) playbooks/02_prepare_rhacm.yml

bgp:
	ansible-playbook -i $(INVENTORY) playbooks/03_phoenixnap_bgp.yml

provision:
	ansible-playbook -i $(INVENTORY) playbooks/04_provision_servers.yml

dns:
	ansible-playbook -i $(INVENTORY) playbooks/05_cloudflare_dns.yml

install:
	ansible-playbook -i $(INVENTORY) playbooks/06_wait_and_export.yml

virt:
	ansible-playbook -i $(INVENTORY) playbooks/07_virtualization.yml

evpn:
	ansible-playbook -i $(INVENTORY) playbooks/08_evpn.yml

status:
	ansible-playbook -i $(INVENTORY) playbooks/09_status.yml

deploy:
	ansible-playbook -i $(INVENTORY) site.yml

destroy:
	ansible-playbook -i $(INVENTORY) destroy.yml -e confirm_destroy=true

lint:
	ansible-lint site.yml destroy.yml playbooks/*.yml
