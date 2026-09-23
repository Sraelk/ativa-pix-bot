# ATIVA PIX BOT - pacote completo

## O que está incluído
- Cadastro automático de usuários
- Menu com botões
- Campanha configurável no banco SQLite
- Registro de ativações por comprovante
- Aprovação/rejeição pelo administrador
- Recompensa liberada ao atingir a meta
- Saldo e histórico básico
- Link de indicação
- Solicitação de saque via Pix
- Aprovação/rejeição de saques pelo administrador
- Painel administrativo e estatísticas
- Proteções básicas contra duplicidade de indicação

## Importante
O BotFather NÃO recebe este código. Ele apenas cria o bot e fornece o token.
O código precisa rodar em um computador/servidor/hosting que tenha Python.

## Configuração
1. No Telegram, abra @BotFather.
2. Use /newbot e crie "Ativa Pix Bot".
3. Copie o TOKEN fornecido pelo BotFather.
4. Descubra seu Telegram ID com um bot de identificação de ID.
5. Instale:
   pip install -r requirements.txt
6. Defina:
   BOT_TOKEN=seu_token
   ADMIN_IDS=seu_id
7. Execute:
   python bot.py

### Linux / Termux
export BOT_TOKEN="SEU_TOKEN"
export ADMIN_IDS="123456789"
python bot.py

### Windows PowerShell
$env:BOT_TOKEN="SEU_TOKEN"
$env:ADMIN_IDS="123456789"
python bot.py

## Fluxo de ativação
Usuário entra -> participa da campanha -> realiza a ação descrita -> envia comprovante.
O administrador recebe o comprovante e pode aprovar/rejeitar.
Ao atingir a meta da campanha, a recompensa é creditada uma única vez.

## Saques
O usuário informa a chave Pix e o pedido fica pendente. O administrador aprova ou rejeita.
O código NÃO faz transferência bancária automática.

## Segurança
Nunca peça senha bancária, código SMS, token de autenticação ou acesso à conta do usuário.
Use somente campanhas legítimas e deixe valores, critérios, prazos e condições explícitos.
