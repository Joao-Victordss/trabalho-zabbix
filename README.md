# Trabalho Pratico: Zabbix com Docker Compose

Este projeto monta um ambiente academico de monitoramento com Zabbix usando Docker Compose. A proposta e simular um cenario realista com um servidor gerente Zabbix e um host Linux separado, monitorando Disco, CPU, Memoria e o servico Squid.

O ambiente tambem inclui triggers, graficos, orientacao para notificacao por Telegram e uma acao remota para iniciar o Squid automaticamente quando ele estiver parado.

## Arquitetura

Servicos criados pelo `docker-compose.yml`:

| Servico | Funcao |
| --- | --- |
| `mysql-server` | Banco de dados usado pelo Zabbix Server e Zabbix Web |
| `zabbix-server` | Servidor gerente que coleta dados, avalia triggers e executa acoes |
| `zabbix-web` | Interface web do Zabbix, acessivel em `http://localhost:8080` |
| `host-monitorado` | Container Linux separado, com `zabbix-agent2`, Squid, Supervisor e scripts de teste |

Todos os containers ficam na rede Docker `zabbix-net`. O host monitorado usa o hostname `linux-monitorado`.

## Por que separar gerente e host monitorado?

Em monitoramento de servicos, o gerente e o alvo monitorado devem ser entidades diferentes. Isso deixa claro o papel de cada componente:

- O `zabbix-server` representa o sistema central de monitoramento.
- O `host-monitorado` representa uma maquina Linux com servicos e recursos a serem observados.
- O `zabbix-agent2` roda no host monitorado e entrega metricas ao gerente.

Essa separacao ajuda a demonstrar, academicamente, que o Zabbix nao monitora apenas a si mesmo. Ele coleta dados de outro host, aplica templates, dispara triggers e pode executar acoes remotas.

## Estrutura do projeto

```text
.
├── docker-compose.yml
├── .env.example
├── README.md
├── zabbix
│   ├── api
│   │   └── provision.py
│   └── scripts
│       └── provision.sh
└── monitored-host
    ├── Dockerfile
    ├── zabbix_agent2.conf
    ├── supervisord.conf
    └── scripts
        ├── start-squid.sh
        ├── stop-squid.sh
        ├── stress-cpu.sh
        ├── stress-memory.sh
        ├── fill-disk.sh
        └── clean-disk.sh
```

## Requisitos

- Docker
- Docker Compose v2
- Python 3 no computador local, apenas para executar o provisionamento via API

## Subindo o ambiente

Copie o arquivo de exemplo de variaveis:

```bash
cp .env.example .env
```

Suba os containers:

```bash
docker compose up -d --build
```

Acompanhe os logs do Zabbix Server:

```bash
docker compose logs -f zabbix-server
```

O primeiro boot pode demorar alguns minutos, pois o Zabbix cria e atualiza o schema do banco MySQL.

## Acesso ao Zabbix Web

Acesse:

```text
http://localhost:8080
```

Credenciais padrao:

```text
Usuario: Admin
Senha: zabbix
```

## Provisionamento automatico via API

O script `zabbix/api/provision.py` cria automaticamente:

- grupo `TP-Zabbix`
- template `TP - Monitoramento Personalizado`
- host `linux-monitorado`
- itens de Disco, CPU, Memoria e Squid
- triggers
- graficos
- acao remota `TP - Iniciar Squid automaticamente`, quando a versao da API aceitar os parametros de comando remoto

Execute:

```bash
python3 zabbix/api/provision.py
```

Ou:

```bash
bash zabbix/scripts/provision.sh
```

Variaveis usadas pelo script:

```bash
export ZABBIX_URL=http://localhost:8080/api_jsonrpc.php
export ZABBIX_USER=Admin
export ZABBIX_PASSWORD=zabbix
python3 zabbix/api/provision.py
```

O script e idempotente: se grupo, template, host, itens, triggers ou graficos ja existirem, ele tenta atualizar em vez de duplicar.

## Configuracao do host monitorado

Arquivo principal: `monitored-host/zabbix_agent2.conf`.

Configuracoes importantes:

```text
Server=zabbix-server
ServerActive=zabbix-server
Hostname=linux-monitorado
AllowKey=system.run[/usr/local/bin/start-squid.sh,*]
Plugins.SystemRun.LogRemoteCommands=1
```

O container nao usa `systemd`. Por isso, o Squid e o Zabbix Agent2 sao gerenciados pelo Supervisor, configurado em `monitored-host/supervisord.conf`.

Para entrar no container:

```bash
docker exec -it host-monitorado bash
```

Para consultar processos:

```bash
supervisorctl status
```

## Itens criados no template

### Disco

| Nome | Key | Unidade | Tag |
| --- | --- | --- | --- |
| Disco: espaco livre | `vfs.fs.size[/,free]` | B | `component=Disco` |
| Disco: espaco usado | `vfs.fs.size[/,used]` | B | `component=Disco` |
| Disco: espaco total | `vfs.fs.size[/,total]` | B | `component=Disco` |
| Disco: percentual usado | `vfs.fs.size[/,pused]` | `%` | `component=Disco` |

### CPU

| Nome | Key | Tipo | Unidade | Tag |
| --- | --- | --- | --- | --- |
| CPU: ociosidade media 1min | `system.cpu.util[,idle,avg1]` | Zabbix agent | `%` | `component=CPU` |
| CPU: utilizacao | `custom.cpu.util.pused` | Calculated | `%` | `component=CPU` |

Formula do item calculado:

```text
100-last(//system.cpu.util[,idle,avg1])
```

### Memoria

| Nome | Key | Unidade | Tag |
| --- | --- | --- | --- |
| Memoria: utilizacao | `vm.memory.size[pused]` | `%` | `component=Memoria` |
| Memoria: total | `vm.memory.size[total]` | B | `component=Memoria` |
| Memoria: livre | `vm.memory.size[free]` | B | `component=Memoria` |

### Servico

| Nome | Key | Unidade | Tag |
| --- | --- | --- | --- |
| Servico Squid: processos em execucao | `proc.num[squid]` | processos | `component=Servico` |

## Triggers criadas

Todas as triggers recebem a tag:

```text
scope=tp-zabbix
```

| Nome | Severidade | Expressao |
| --- | --- | --- |
| Disco: uso maior que 50% e menor que 60% | High | `min(/TP - Monitoramento Personalizado/vfs.fs.size[/,pused],1m)>50 and max(/TP - Monitoramento Personalizado/vfs.fs.size[/,pused],1m)<60` |
| Disco: uso maior que 60% | Disaster | `min(/TP - Monitoramento Personalizado/vfs.fs.size[/,pused],1m)>60` |
| CPU: utilizacao maior que 30% por 1 minuto | High | `min(/TP - Monitoramento Personalizado/custom.cpu.util.pused,1m)>30` |
| Memoria: utilizacao maior que 30% por 1 minuto | High | `min(/TP - Monitoramento Personalizado/vm.memory.size[pused],1m)>30` |
| Squid: servico parado | Disaster | `max(/TP - Monitoramento Personalizado/proc.num[squid],1m)=0` |

## Graficos criados

| Grafico | Itens |
| --- | --- |
| Grafico Disco - Espaco | Disco livre, usado e total |
| Grafico CPU - Utilizacao | CPU: utilizacao |
| Grafico Memoria - Capacidade | Memoria total e livre |
| Grafico Memoria - Utilizacao | Memoria: utilizacao |

## Testes praticos

### Teste do Squid parado

Pare o Squid:

```bash
docker exec -it host-monitorado /usr/local/bin/stop-squid.sh
```

No Zabbix, aguarde a coleta do item `proc.num[squid]`. A trigger `Squid: servico parado` deve entrar em problema.

Para iniciar manualmente:

```bash
docker exec -it host-monitorado /usr/local/bin/start-squid.sh
```

### Teste de CPU

```bash
docker exec -it host-monitorado /usr/local/bin/stress-cpu.sh
```

O script usa `stress-ng` por 180 segundos por padrao. Para alterar:

```bash
docker exec -it -e DURATION=300 -e WORKERS=4 host-monitorado /usr/local/bin/stress-cpu.sh
```

### Teste de memoria

```bash
docker exec -it host-monitorado /usr/local/bin/stress-memory.sh
```

Padrao: 512 MB por 180 segundos. Para alterar:

```bash
docker exec -it -e BYTES=1G -e DURATION=300 host-monitorado /usr/local/bin/stress-memory.sh
```

### Teste de disco

Crie arquivo temporario grande:

```bash
docker exec -it host-monitorado /usr/local/bin/fill-disk.sh
```

Padrao: arquivo de 2048 MB em `/var/tmp/tp-zabbix`.

Para alterar o tamanho:

```bash
docker exec -it -e SIZE_MB=4096 host-monitorado /usr/local/bin/fill-disk.sh
```

Limpe os arquivos temporarios:

```bash
docker exec -it host-monitorado /usr/local/bin/clean-disk.sh
```

## Telegram no Zabbix

Este projeto nao inclui token real de Telegram. A configuracao deve ser feita manualmente no Zabbix Web.

### Criar o bot

1. Abra o Telegram e converse com `@BotFather`.
2. Use o comando `/newbot`.
3. Escolha nome e usuario para o bot.
4. Copie o token gerado.

### Obter o chat_id

Uma forma simples:

1. Envie uma mensagem qualquer para o bot criado.
2. Acesse no navegador, trocando `TOKEN_DO_BOT` pelo token real:

```text
https://api.telegram.org/botTOKEN_DO_BOT/getUpdates
```

3. Procure o campo `chat.id`.

### Configurar Media type

No Zabbix:

1. Acesse `Alerts > Media types`.
2. Abra `Telegram`.
3. Configure o token do bot.
4. Salve.

### Adicionar Telegram ao usuario Admin

1. Acesse `Users > Users`.
2. Abra o usuario `Admin`.
3. Va em `Media`.
4. Adicione uma media do tipo `Telegram`.
5. Informe o `chat_id`.
6. Marque severidades `High` e `Disaster`.

### Criar Action para Telegram

Crie uma Action para problemas:

- Nome sugerido: `TP - Notificar Telegram`
- Condicao recomendada: `Event tag scope equals tp-zabbix`
- Condicao adicional opcional: severidade igual a `High` ou `Disaster`
- Operacao: enviar mensagem para o usuario `Admin` usando media `Telegram`

Mensagem sugerida:

```text
Problema: {EVENT.NAME}
Severidade: {EVENT.SEVERITY}
Host: {HOST.NAME}
Valor: {ITEM.VALUE1}
Data/Hora: {EVENT.DATE} {EVENT.TIME}
```

Mensagem de recuperacao sugerida:

```text
Recuperado: {EVENT.NAME}
Severidade: {EVENT.SEVERITY}
Host: {HOST.NAME}
Valor atual: {ITEM.VALUE1}
Data/Hora: {EVENT.RECOVERY.DATE} {EVENT.RECOVERY.TIME}
```

Ative tambem a opcao de operacao de recuperacao na Action, para que o Zabbix envie mensagem quando o problema for resolvido.

## Acao remota para iniciar o Squid

Nome da Action:

```text
TP - Iniciar Squid automaticamente
```

Condicao:

```text
Trigger = Squid: servico parado
```

Operacao:

```text
Executar comando remoto no host atual:
/usr/local/bin/start-squid.sh
```

Observacao importante: em Docker, o container nao roda `systemd`. Portanto, o comando remoto nao deve usar `systemctl`. O controle do Squid e feito por Supervisor:

```bash
supervisorctl start squid
supervisorctl stop squid
```

O Agent2 permite apenas o comando remoto definido em `AllowKey`:

```text
AllowKey=system.run[/usr/local/bin/start-squid.sh,*]
```

Isso evita liberar comandos arbitrarios para execucao remota.

O script de provisionamento tenta criar a Action automaticamente via API. Se a sua versao do Zabbix recusar os parametros de comando remoto, crie a Action manualmente seguindo os passos acima.

## Prints recomendados para entrega

Tire prints dos seguintes pontos:

- Docker Compose rodando, por exemplo com `docker compose ps`
- tela de login ou dashboard do Zabbix Web
- host `linux-monitorado` cadastrado no Zabbix
- grupo `TP-Zabbix`
- template `TP - Monitoramento Personalizado`
- itens de Disco, CPU, Memoria e Servico
- triggers com tag `scope=tp-zabbix`
- graficos criados no template
- alerta recebido no Telegram
- trigger `Squid: servico parado` em estado de problema
- Action remota `TP - Iniciar Squid automaticamente`
- Squid ativo novamente apos a acao remota

## Limitacoes do Docker em relacao a uma VM

Este laboratorio usa containers para facilitar reproducao e entrega academica. Existem diferencas importantes em relacao a uma maquina virtual:

- Containers compartilham o kernel do host, enquanto VMs possuem kernel proprio.
- Algumas metricas de CPU, memoria e disco podem refletir limites e comportamento do container, nao de uma maquina completa.
- O container nao usa `systemd`, por isso os servicos sao gerenciados por Supervisor.
- Testes de disco dependem do espaco disponivel no host Docker e do volume usado.
- Em ambientes reais, o Zabbix Agent normalmente roda direto no sistema operacional monitorado.

Mesmo com essas limitacoes, o projeto demonstra os conceitos principais: coleta de metricas, template personalizado, triggers, graficos, notificacao e acao remota.

## Explicacao academica das tarefas

### Monitoramento de disco

Os itens de disco permitem observar espaco livre, usado, total e percentual usado. As triggers de 50% a 60% e acima de 60% simulam niveis diferentes de criticidade.

### Monitoramento de CPU

O Agent2 coleta a ociosidade media da CPU em 1 minuto. O template cria um item calculado para transformar o valor em utilizacao:

```text
Utilizacao = 100 - ociosidade
```

Isso facilita a criacao de trigger quando a CPU estiver acima de 30%.

### Monitoramento de memoria

O item `vm.memory.size[pused]` representa o percentual de memoria usada. A trigger de 30% foi escolhida para facilitar a demonstracao em laboratorio.

### Monitoramento do Squid

O item `proc.num[squid]` conta processos do Squid. Quando o valor chega a zero, o Zabbix entende que o servico esta parado e dispara uma trigger Disaster.

### Notificacao

O Telegram representa a etapa de comunicacao com o administrador. Em um ambiente real, essa notificacao permite resposta rapida a incidentes.

### Acao remota

A acao remota mostra automacao operacional. Quando o Squid para, o Zabbix pode executar `/usr/local/bin/start-squid.sh` no host monitorado para tentar restaurar o servico.

## Comandos principais

```bash
docker compose up -d --build
docker compose logs -f zabbix-server
docker exec -it host-monitorado bash
docker exec -it host-monitorado /usr/local/bin/stop-squid.sh
docker exec -it host-monitorado /usr/local/bin/stress-cpu.sh
docker exec -it host-monitorado /usr/local/bin/stress-memory.sh
docker exec -it host-monitorado /usr/local/bin/fill-disk.sh
docker exec -it host-monitorado /usr/local/bin/clean-disk.sh
```
