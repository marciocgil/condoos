#!/usr/bin/env bash
# One-time preparation of a fresh Ubuntu LTS VPS for the CondoOS (docs/deploy.md, 9).
# Run as root, once:  bash setup-server.sh
# - security updates installed automatically;
# - firewall: only SSH, HTTP and HTTPS;
# - SSH by key only (root's authorized key is copied to the user "condoos"), no root login;
# - Docker Engine from Docker's official repository;
# - 4 GB of swap (image builds with Docling need memory).
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "Rode como root." >&2; exit 1; fi
if [ ! -s /root/.ssh/authorized_keys ]; then
  echo "Nenhuma chave SSH em /root/.ssh/authorized_keys: adicione a chave antes (painel da Hostinger)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get -y upgrade
apt-get -y install ca-certificates curl git ufw unattended-upgrades openssl
dpkg-reconfigure -f noninteractive unattended-upgrades

# Firewall.
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

# Docker Engine (official repository).
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
. /etc/os-release
codename="${UBUNTU_CODENAME:-$VERSION_CODENAME}"
# A brand-new Ubuntu release may not be in Docker's repository yet: fall back to 24.04 (noble).
if ! curl -fsI "https://download.docker.com/linux/ubuntu/dists/${codename}/Release" >/dev/null; then
  echo "Repositório do Docker ainda sem ${codename}; usando noble (24.04)."
  codename=noble
fi
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${codename} stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
# Docker publishes ports past ufw; only Caddy publishes any (80/443), PostgreSQL publishes none.

# User that runs the system.
if ! id condoos >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" condoos
fi
usermod -aG docker,sudo condoos
install -d -m 700 -o condoos -g condoos /home/condoos/.ssh
install -m 600 -o condoos -g condoos /root/.ssh/authorized_keys /home/condoos/.ssh/authorized_keys
echo "condoos ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/condoos
chmod 440 /etc/sudoers.d/condoos

# SSH: key only, no root login. sshd keeps the FIRST value it reads, and the provider's image
# ships files like 50-cloud-init.conf with "PasswordAuthentication yes": ours must sort first.
rm -f /etc/ssh/sshd_config.d/90-condoos.conf
cat > /etc/ssh/sshd_config.d/00-condoos.conf <<'SSH'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
SSH
sshd -t
systemctl reload ssh || systemctl reload sshd
# Fail loudly if another file still wins.
sshd -T | grep -qx "passwordauthentication no" || { echo "SSH ainda aceita senha" >&2; exit 1; }
sshd -T | grep -qx "permitrootlogin no" || { echo "SSH ainda aceita root" >&2; exit 1; }

# Swap.
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 4G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
fi

echo
echo "Pronto. A partir de agora entre com:  ssh condoos@$(hostname -I | awk '{print $1}')"
echo "O login de root e por senha foi desligado."
