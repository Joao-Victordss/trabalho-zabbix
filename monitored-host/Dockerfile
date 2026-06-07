FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        gnupg \
        iproute2 \
        procps \
        squid \
        stress-ng \
        supervisor \
    && curl -fsSL https://repo.zabbix.com/zabbix/7.0/ubuntu/pool/main/z/zabbix-release/zabbix-release_latest_7.0+ubuntu24.04_all.deb -o /tmp/zabbix-release.deb \
    && dpkg -i /tmp/zabbix-release.deb \
    && apt-get update \
    && apt-get install -y --no-install-recommends zabbix-agent2 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/zabbix-release.deb

COPY zabbix_agent2.conf /etc/zabbix/zabbix_agent2.conf
COPY supervisord.conf /etc/supervisor/conf.d/tp-zabbix.conf
COPY scripts/*.sh /usr/local/bin/

RUN mkdir -p /var/log/supervisor /var/log/squid /var/spool/squid /var/tmp/tp-zabbix \
    && chown -R proxy:proxy /var/log/squid /var/spool/squid \
    && chmod +x /usr/local/bin/*.sh \
    && squid -z

EXPOSE 10050 3128

CMD ["/usr/bin/supervisord", "-n", "-c", "/etc/supervisor/supervisord.conf"]
