import telebot
from telebot import types
import sqlite3
import json
import hashlib
from datetime import datetime, timedelta
import threading
import time
import schedule
import requests
import random
import string
from typing import Dict, List, Tuple
import logging
import pytz
from decimal import Decimal
import os

# ================= CONFIGURAÇÃO COM SEUS DADOS =================
TOKEN = '8255460383:AAG1znCT140k8Kidh7LXFtops4F0n77ckVo'
ADMIN_ID = 5125563829  # SEU ID DO TELEGRAM
ADMIN_USERNAME = '@AiltonArmindo'
ADMIN_EMAIL = 'ayltonanna@gmail.com'
BOT_USERNAME = '@BetMasterProBot'
SUPPORT_WHATSAPP = '+258 84 856 8229'

# Preços dos planos VIP (em MT)
PRECOS = {
    'daily': {'nome': 'VIP Diário', 'preco': 150, 'dias': 1, 'codigos_dia': 10},
    'weekly': {'nome': 'VIP Semanal', 'preco': 800, 'dias': 7, 'codigos_dia': 15},
    'monthly': {'nome': 'VIP Mensal', 'preco': 2500, 'dias': 30, 'codigos_dia': 20},
    'premium': {'nome': 'VIP Premium', 'preco': 5000, 'dias': 90, 'codigos_dia': 30}
}

# Informações de pagamento - SEUS DADOS
PAYMENT_INFO = {
    'emola': '870612404 - Ailton Armindo',
    'mpesa': '848568229 - Ailton Armindo',
    'paypal': ADMIN_EMAIL,
    'whatsapp': SUPPORT_WHATSAPP,
    'telegram': ADMIN_USERNAME,
    'email': ADMIN_EMAIL
}

bot = telebot.TeleBot(TOKEN, parse_mode='HTML', threaded=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ================= BANCO DE DADOS AVANÇADO =================
def init_database():
    """Inicializa o banco de dados com todas as tabelas"""
    conn = sqlite3.connect('betmaster_v2.db', check_same_thread=False)
    cursor = conn.cursor()
    
    # Tabela de usuários
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        full_name TEXT,
        is_vip INTEGER DEFAULT 0,
        vip_type TEXT,
        vip_until TEXT,
        daily_codes_used INTEGER DEFAULT 0,
        daily_codes_limit INTEGER DEFAULT 2,
        total_codes_created INTEGER DEFAULT 0,
        credits DECIMAL(10,2) DEFAULT 0.00,
        balance DECIMAL(10,2) DEFAULT 0.00,
        total_spent DECIMAL(10,2) DEFAULT 0.00,
        total_won DECIMAL(10,2) DEFAULT 0.00,
        referral_code TEXT UNIQUE,
        referred_by INTEGER,
        referral_count INTEGER DEFAULT 0,
        referral_earnings DECIMAL(10,2) DEFAULT 0.00,
        created_at TEXT,
        last_active TEXT,
        notifications INTEGER DEFAULT 1,
        language TEXT DEFAULT 'pt'
    )
    ''')
    
    # Tabela de códigos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS codes (
        code_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        code TEXT UNIQUE,
        bet_type TEXT,
        event TEXT,
        prediction TEXT,
        odds DECIMAL(5,2),
        stake DECIMAL(10,2),
        potential_win DECIMAL(10,2),
        status TEXT DEFAULT 'pending',
        result TEXT,
        created_at TEXT,
        won_amount DECIMAL(10,2) DEFAULT 0.00,
        is_free INTEGER DEFAULT 1,
        casa_aposta TEXT,
        is_winner INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Tabela de pagamentos
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        payment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        amount DECIMAL(10,2),
        payment_method TEXT,
        transaction_id TEXT UNIQUE,
        status TEXT DEFAULT 'pending',
        created_at TEXT,
        approved_at TEXT,
        approved_by INTEGER,
        plan_type TEXT,
        proof_image TEXT,
        notes TEXT
    )
    ''')
    
    # Tabela de previsões
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS predictions (
        prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
        event TEXT,
        league TEXT,
        home_team TEXT,
        away_team TEXT,
        prediction TEXT,
        prediction_type TEXT,
        odds DECIMAL(5,2),
        confidence INTEGER,
        analysis TEXT,
        status TEXT DEFAULT 'upcoming',
        result TEXT,
        created_at TEXT,
        match_time TEXT,
        is_premium INTEGER DEFAULT 0,
        success_rate INTEGER
    )
    ''')
    
    # Tabela de estatísticas
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS statistics (
        stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
        stat_date TEXT,
        total_users INTEGER DEFAULT 0,
        new_users INTEGER DEFAULT 0,
        active_users INTEGER DEFAULT 0,
        vip_users INTEGER DEFAULT 0,
        total_codes INTEGER DEFAULT 0,
        free_codes INTEGER DEFAULT 0,
        vip_codes INTEGER DEFAULT 0,
        total_predictions INTEGER DEFAULT 0,
        total_revenue DECIMAL(10,2) DEFAULT 0.00,
        total_withdrawals DECIMAL(10,2) DEFAULT 0.00,
        created_at TEXT
    )
    ''')
    
    # Tabela de logs admin
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        admin_id INTEGER,
        action TEXT,
        target_user_id INTEGER,
        details TEXT,
        created_at TEXT
    )
    ''')
    
    # Tabela de suporte
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS support_tickets (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        subject TEXT,
        message TEXT,
        status TEXT DEFAULT 'open',
        admin_response TEXT,
        created_at TEXT,
        resolved_at TEXT,
        resolved_by INTEGER
    )
    ''')
    
    # Tabela de notificações
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS notifications (
        notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT,
        notification_type TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT
    )
    ''')
    
    conn.commit()
    logger.info("Banco de dados inicializado com sucesso!")
    return conn, cursor

# Inicializar banco de dados
conn, cursor = init_database()

# ================= SISTEMA DE CÓDIGOS =================
class CodeSystem:
    @staticmethod
    def generate_code(user_id: int, bet_type: str = "normal") -> str:
        """Gera um código único para aposta"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"BM{user_id:04d}{timestamp[-6:]}{random_str}"
    
    @staticmethod
    def can_generate_free_code(user_id: int) -> Tuple[bool, str, int]:
        """Verifica se usuário pode gerar código grátis"""
        cursor.execute('SELECT daily_codes_used, daily_codes_limit, is_vip FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            return False, "Usuário não encontrado", 0
        
        daily_used, daily_limit, is_vip = user
        remaining = daily_limit - daily_used
        
        if remaining <= 0:
            if is_vip:
                return False, f"❌ Limite VIP atingido hoje! ({daily_used}/{daily_limit})\n💎 Use /comprar para mais códigos amanhã!", 0
            else:
                return False, f"❌ LIMITE DIÁRIO ATINGIDO! (2/2)\n\n💎 <b>Torne-se VIP para:</b>\n• {PRECOS['daily']['codigos_dia']} códigos/dia\n• Palpites Premium\n• Suporte Prioritário\n\n👉 Use /vip para ver planos!", 0
        
        return True, f"✅ Você pode gerar {remaining} código(s) hoje", remaining

# ================= SISTEMA VIP =================
class VIPSystem:
    @staticmethod
    def check_vip_status(user_id: int) -> Dict:
        """Verifica status VIP do usuário"""
        cursor.execute('''
            SELECT is_vip, vip_type, vip_until, daily_codes_limit, username 
            FROM users WHERE user_id = ?
        ''', (user_id,))
        
        result = cursor.fetchone()
        if not result:
            return {'is_vip': False, 'username': 'N/A'}
        
        is_vip, vip_type, vip_until, codes_limit, username = result
        
        if is_vip and vip_until:
            try:
                vip_until_date = datetime.strptime(vip_until, '%Y-%m-%d %H:%M:%S')
                if vip_until_date < datetime.now():
                    # VIP expirado
                    cursor.execute('''
                        UPDATE users 
                        SET is_vip = 0, vip_type = NULL, vip_until = NULL, daily_codes_limit = 2 
                        WHERE user_id = ?
                    ''', (user_id,))
                    conn.commit()
                    return {'is_vip': False, 'username': username}
            except:
                pass
        
        return {
            'is_vip': bool(is_vip),
            'vip_type': vip_type,
            'vip_until': vip_until,
            'daily_codes_limit': codes_limit,
            'username': username
        }
    
    @staticmethod
    def activate_vip(user_id: int, plan_type: str, admin_id: int = None):
        """Ativa VIP para usuário"""
        plan = PRECOS.get(plan_type)
        if not plan:
            return False
        
        vip_until = datetime.now() + timedelta(days=plan['dias'])
        
        cursor.execute('''
            UPDATE users 
            SET is_vip = 1, vip_type = ?, vip_until = ?, daily_codes_limit = ?, daily_codes_used = 0
            WHERE user_id = ?
        ''', (plan_type, vip_until.strftime('%Y-%m-%d %H:%M:%S'), plan['codigos_dia'], user_id))
        
        # Registrar log
        if admin_id:
            cursor.execute('''
                INSERT INTO admin_logs (admin_id, action, target_user_id, details, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (admin_id, 'activate_vip', user_id, 
                  f'Plano {plan_type} ativado até {vip_until}', datetime.now()))
        
        conn.commit()
        
        # Enviar notificação ao usuário
        try:
            plan_name = plan['nome']
            bot.send_message(
                user_id,
                f"🎉 <b>VIP ATIVADO COM SUCESSO!</b>\n\n"
                f"💎 Plano: <b>{plan_name}</b>\n"
                f"📅 Validade: <b>{vip_until.strftime('%d/%m/%Y')}</b>\n"
                f"🔢 Códigos/dia: <b>{plan['codigos_dia']}</b>\n"
                f"💰 Preço: <b>{plan['preco']}MT</b>\n\n"
                f"🎯 Agora você tem acesso completo a todos os recursos premium!\n\n"
                f"Use /gerar para criar seus códigos VIP!"
            )
        except:
            pass
        
        return True

# ================= GERADOR DE PREDIÇÕES =================
class PredictionGenerator:
    def __init__(self):
        self.sports_data = {
            'futebol': {
                'leagues': ['Premier League', 'La Liga', 'Serie A', 'Bundesliga', 'Ligue 1', 'Liga NOS'],
                'teams': {
                    'Premier League': ['Manchester City', 'Liverpool', 'Chelsea', 'Arsenal', 'Manchester Utd', 'Tottenham'],
                    'La Liga': ['Real Madrid', 'Barcelona', 'Atlético Madrid', 'Sevilla', 'Valencia', 'Villarreal'],
                    'Serie A': ['Inter Milan', 'AC Milan', 'Juventus', 'Napoli', 'Roma', 'Lazio'],
                    'Bundesliga': ['Bayern Munich', 'Borussia Dortmund', 'RB Leipzig', 'Bayer Leverkusen'],
                    'Ligue 1': ['PSG', 'Marseille', 'Lyon', 'Monaco'],
                    'Liga NOS': ['Benfica', 'Porto', 'Sporting', 'Braga']
                },
                'predictions': ['1', 'X', '2', 'Over 2.5', 'Under 2.5', 'BTTS Sim', 'BTTS Não', 'Dupla Chance 1X', 'Dupla Chance X2']
            },
            'basquete': {
                'leagues': ['NBA', 'EuroLeague', 'ACB'],
                'predictions': ['Casa', 'Fora', 'Over', 'Under', 'Handicap']
            },
            'tenis': {
                'leagues': ['ATP', 'WTA', 'Grand Slam'],
                'predictions': ['Vitória Jogador 1', 'Vitória Jogador 2', 'Total Games Over', 'Total Games Under']
            }
        }
    
    def generate_daily_predictions(self, count: int = 5) -> List[Dict]:
        """Gera previsões diárias"""
        predictions = []
        
        for _ in range(count):
            sport = random.choice(['futebol'])
            league = random.choice(self.sports_data[sport]['leagues'])
            
            if sport == 'futebol':
                teams = self.sports_data[sport]['teams'][league]
                home, away = random.sample(teams, 2)
                event = f"{home} vs {away}"
                
                prediction_type = random.choice(['1X2', 'Over/Under', 'BTTS'])
                
                if prediction_type == '1X2':
                    pred = random.choice(['1', 'X', '2'])
                    odds = random.uniform(1.5, 3.5)
                elif prediction_type == 'Over/Under':
                    pred = random.choice(['Over 2.5', 'Under 2.5'])
                    odds = random.uniform(1.6, 2.2)
                else:  # BTTS
                    pred = random.choice(['Sim', 'Não'])
                    odds = random.uniform(1.6, 2.3)
                
                confidence = random.randint(70, 89)
                
                predictions.append({
                    'sport': sport,
                    'league': league,
                    'event': event,
                    'prediction': pred,
                    'type': prediction_type,
                    'odds': round(odds, 2),
                    'confidence': confidence,
                    'analysis': self.generate_analysis(home, away, pred, league),
                    'match_time': f"{random.randint(15, 22)}:00"
                })
        
        return predictions

    def generate_analysis(self, home: str, away: str, prediction: str, league: str) -> str:
        """Gera análise para a previsão"""
        analyses = [
            f"🏟️ <b>Análise do Jogo:</b>\n{home} joga em casa com vantagem estatística. Últimos 5 jogos: 3V-1E-1D.\n{away} apresenta defesa sólida fora de casa. Expectativa de jogo equilibrado.",
            f"📊 <b>Estatísticas:</b>\nMédia de gols por jogo: {home} - 1.8 | {away} - 1.5\nConfrontos diretos: 4 vitórias {home}, 2 empates, 2 vitórias {away}.",
            f"⚽ <b>Forma Atual:</b>\n{home} vem de 2 vitórias consecutivas.\n{away} não perde há 3 jogos.\nAmbientes propício para gols.",
            f"🎯 <b>Momento das Equipes:</b>\n{home} busca aproximação do topo.\n{away} precisa de pontos para subir.\nJogo de motivação alta para ambos.",
            f"🛡️ <b>Defesas e Ataques:</b>\n{home} ataca bem mas defesa falha.\n{away} tem defesa organizada.\nPossibilidade de ambos marcarem."
        ]
        return random.choice(analyses)

# ================= HANDLERS PRINCIPAIS =================
@bot.message_handler(commands=['start', 'help', 'ajuda'])
def start_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
    
    # Registrar/atualizar usuário
    cursor.execute('''
        INSERT OR IGNORE INTO users 
        (user_id, username, full_name, created_at, last_active, referral_code) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, full_name, datetime.now(), datetime.now(), 
          f"REF{user_id:06d}"))
    
    cursor.execute('UPDATE users SET last_active = ? WHERE user_id = ?', 
                  (datetime.now(), user_id))
    conn.commit()
    
    # Verificar status VIP
    vip_status = VIPSystem.check_vip_status(user_id)
    
    # Texto de boas-vindas
    welcome_text = f"""
🏆 <b>BET MASTER PRO - SEU ASSISTENTE DE APOSTAS</b>

👋 <b>Olá, {full_name}!</b>
🆔 <b>Seu ID:</b> <code>{user_id}</code>

💎 <b>STATUS ATUAL:</b> {'<b>VIP 🎖️ ' + vip_status['vip_type'].upper() + '</b>' if vip_status['is_vip'] else '<b>GRÁTIS ⭐</b>'}
🔢 <b>Códigos disponíveis hoje:</b> {vip_status.get('daily_codes_limit', 2) - get_daily_codes_used(user_id)}/{vip_status.get('daily_codes_limit', 2)}

📊 <b>ESTATÍSTICAS:</b>
• Códigos gerados: {get_user_total_codes(user_id)}
• Palpites seguidos: {random.randint(5, 50)}
• Acertos: {random.randint(40, 85)}%

🎯 <b>PRINCIPAIS COMANDOS:</b>
/gerar - Criar código de aposta (2 grátis/dia)
/palpites - Ver previsões do dia
/vip - Planos VIP e benefícios
/comprar - Comprar plano VIP
/perfil - Meu perfil completo
/suporte - Falar com suporte
/termos - Termos de uso

💰 <b>PLANOS VIP DISPONÍVEIS:</b>
1. Diário - 150MT (10 códigos/dia)
2. Semanal - 800MT (15 códigos/dia)
3. Mensal - 2.500MT (20 códigos/dia)
4. Premium - 5.000MT (30 códigos/dia)

💡 <b>DICA DO DIA:</b> Comece com os 2 códigos grátis e veja nossos resultados antes de investir!

⚠️ <b>AVISO:</b> Apostas envolvem riscos. Jogue com responsabilidade.
"""
    
    # Criar teclado personalizado
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Linha 1: Ações principais
    markup.add(
        types.InlineKeyboardButton("🎯 GERAR CÓDIGO", callback_data="generate_code_main"),
        types.InlineKeyboardButton("💎 VER PLANOS VIP", callback_data="view_plans_main")
    )
    
    # Linha 2: Previsões e Perfil
    markup.add(
        types.InlineKeyboardButton("🔮 PALPITES DO DIA", callback_data="daily_predictions"),
        types.InlineKeyboardButton("👤 MEU PERFIL", callback_data="my_profile_main")
    )
    
    # Linha 3: Suporte e Pagamentos
    markup.add(
        types.InlineKeyboardButton("💰 FORMAS DE PAGAMENTO", callback_data="payment_methods"),
        types.InlineKeyboardButton("📞 SUPORTE 24/7", callback_data="contact_support")
    )
    
    # Linha 4: Admin (se for admin)
    if user_id == ADMIN_ID:
        markup.add(types.InlineKeyboardButton("👑 PAINEL ADMIN", callback_data="admin_panel"))
    
    # Enviar mensagem com foto (se disponível)
    try:
        bot.send_photo(
            message.chat.id,
            photo="https://i.imgur.com/3Q1J9jN.png",  # Substitua por URL da sua imagem
            caption=welcome_text,
            reply_markup=markup,
            parse_mode='HTML'
        )
    except:
        bot.send_message(
            message.chat.id,
            welcome_text,
            reply_markup=markup,
            parse_mode='HTML'
        )
    
    # Registrar log
    log_admin_action(ADMIN_ID, "user_start", user_id, f"Usuário {username} iniciou o bot")

@bot.message_handler(commands=['gerar'])
def generate_code_command(message):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    
    # Verificar se pode gerar código
    can_generate, msg, remaining = CodeSystem.can_generate_free_code(user_id)
    
    if not can_generate:
        # Mostrar opções VIP
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("💎 VER PLANOS VIP", callback_data="view_plans_main"))
        markup.add(types.InlineKeyboardButton("📞 FALAR COM SUPORTE", callback_data="contact_support"))
        
        bot.send_message(
            message.chat.id,
            msg,
            reply_markup=markup,
            parse_mode='HTML'
        )
        return
    
    # Gerar previsão
    generator = PredictionGenerator()
    predictions = generator.generate_daily_predictions(1)
    prediction = predictions[0]
    
    # Gerar código
    code = CodeSystem.generate_code(user_id)
    
    # Salvar no banco
    cursor.execute('''
        INSERT INTO codes (user_id, code, event, prediction, odds, created_at, is_free, casa_aposta)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, code, prediction['event'], prediction['prediction'], 
          prediction['odds'], datetime.now(), 1, 'Betway'))
    
    # Atualizar usuário
    cursor.execute('''
        UPDATE users 
        SET daily_codes_used = daily_codes_used + 1, 
            total_codes_created = total_codes_created + 1,
            last_active = ?
        WHERE user_id = ?
    ''', (datetime.now(), user_id))
    conn.commit()
    
    # Obter dados atualizados
    cursor.execute('SELECT daily_codes_used, daily_codes_limit FROM users WHERE user_id = ?', (user_id,))
    used, limit = cursor.fetchone()
    
    # Gerar mensagem do código
    code_message = f"""
✅ <b>CÓDIGO GERADO COM SUCESSO!</b>

🔢 <b>SEU CÓDIGO:</b> <code>{code}</code>
🎫 <b>TIPO:</b> {'VIP 🎖️' if limit > 2 else 'GRÁTIS ⭐'}
📊 <b>USO HOJE:</b> {used}/{limit} códigos

🏆 <b>PALPITE PREMIUM:</b>
⚽ <b>JOGO:</b> {prediction['event']}
🏅 <b>LIGA:</b> {prediction['league']}
🎯 <b>PREVISÃO:</b> {prediction['prediction']}
📈 <b>ODDS:</b> {prediction['odds']}
💯 <b>CONFIANÇA:</b> {prediction['confidence']}%
🕒 <b>HORÁRIO:</b> {prediction['match_time']}

📋 <b>ANÁLISE:</b>
{prediction['analysis']}

🏠 <b>CASAS RECOMENDADAS:</b>
1. <b>Betway</b> - Use código promocional WELCOME100
2. <b>1xBet</b> - Bônus de 100% até 10.000MT
3. <b>PremierBet</b> - Cashout rápido e seguro
4. <b>ElephantBet</b> - Promoções diárias

💡 <b>COMO USAR:</b>
1. Acesse uma das casas acima
2. Busque pelo jogo: {prediction['event']}
3. Selecione a aposta: {prediction['prediction']}
4. No checkout, use o código: <code>{code}</code>
5. Confirme e boa sorte!

⚠️ <i>Este código é válido por 24 horas. Jogue com responsabilidade.</i>
"""
    
    # Criar botões de ação
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💎 COMPRAR MAIS CÓDIGOS", callback_data="buy_more_codes"),
        types.InlineKeyboardButton("🔮 VER MAIS PALPITES", callback_data="daily_predictions")
    )
    markup.add(
        types.InlineKeyboardButton("📊 MEU HISTÓRICO", callback_data="my_history"),
        types.InlineKeyboardButton("📞 SUPORTE", callback_data="contact_support")
    )
    
    bot.send_message(
        message.chat.id,
        code_message,
        reply_markup=markup,
        parse_mode='HTML'
    )
    
    # Log da ação
    log_admin_action(ADMIN_ID, "code_generated", user_id, f"Código {code} gerado")

@bot.message_handler(commands=['vip'])
def vip_command(message):
    vip_text = f"""
💎 <b>PLANOS VIP BET MASTER PRO</b>

🎯 <b>PORQUE SER VIP?</b>
• Códigos ilimitados (até 30/dia)
• Palpites Premium exclusivos
• Análises detalhadas
• Suporte prioritário 24/7
• Alertas em tempo real
• Estatísticas avançadas
• Grupo VIP exclusivo

💰 <b>PLANOS DISPONÍVEIS:</b>

<b>1. VIP DIÁRIO - 150MT</b>
• 10 códigos por dia
• Acesso a palpites
• Suporte por Telegram
• Validade: 24 horas
• <i>Ideal para teste</i>

<b>2. VIP SEMANAL - 800MT</b>
• 15 códigos por dia
• Todos benefícios Diário
• Análises exclusivas
• Validade: 7 dias
• <i>Melhor custo-benefício</i>

<b>3. VIP MENSAL - 2.500MT</b>
• 20 códigos por dia
• Todos benefícios Semanal
• Conteúdo premium
• Grupo VIP exclusivo
• Validade: 30 dias
• <i>Mais popular</i>

<b>4. VIP PREMIUM - 5.000MT</b>
• 30 códigos por dia
• Todos benefícios Mensal
• Mentoria pessoal
• Alertas instantâneos
• Validade: 90 dias
• <i>Para profissionais</i>

📊 <b>ESTATÍSTICAS VIP:</b>
• Taxa de acerto: 72-85%
• ROI médio: +15-25%
• Usuários satisfeitos: 94%

📲 <b>FORMAS DE PAGAMENTO:</b>
• <b>Emola:</b> {PAYMENT_INFO['emola']}
• <b>M-Pesa:</b> {PAYMENT_INFO['mpesa']}
• <b>PayPal:</b> {PAYMENT_INFO['paypal']}
• <b>WhatsApp:</b> {PAYMENT_INFO['whatsapp']}

⚡ <b>COMO COMPRAR:</b>
1. Escolha seu plano
2. Faça pagamento via método escolhido
3. Envie comprovante para @{ADMIN_USERNAME[1:]}
4. Aguarde ativação (5-15 minutos)
5. Receba confirmação no bot

🎁 <b>BÔNUS EXCLUSIVOS:</b>
• 1ª compra: +1 dia grátis
• Indique amigo: 10% de desconto
• Renovação: 5% de desconto

💡 <i>Comece com o plano Diário para testar!</i>
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Botões para cada plano
    buttons = []
    for plan_id, plan in PRECOS.items():
        buttons.append(
            types.InlineKeyboardButton(
                f"{plan['nome']} - {plan['preco']}MT",
                callback_data=f"buy_plan_{plan_id}"
            )
        )
    
    # Organizar em linhas de 2
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    # Botões adicionais
    markup.add(
        types.InlineKeyboardButton("📞 FALAR COM VENDEDOR", url=f"https://t.me/{ADMIN_USERNAME[1:]}")
    )
    markup.add(
        types.InlineKeyboardButton("💬 WHATSAPP DIRETO", url=f"https://wa.me/{SUPPORT_WHATSAPP.replace('+', '')}")
    )
    
    bot.send_message(
        message.chat.id,
        vip_text,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(commands=['comprar'])
def buy_command(message):
    # Redirecionar para o comando VIP
    vip_command(message)

@bot.message_handler(commands=['palpites'])
def predictions_command(message):
    generator = PredictionGenerator()
    predictions = generator.generate_daily_predictions(3)
    
    predictions_text = f"""
🔮 <b>PALPITES DO DIA - {datetime.now().strftime('%d/%m/%Y')}</b>

🎯 <b>Previsões selecionadas por nossa IA:</b>
"""
    
    for i, pred in enumerate(predictions, 1):
        predictions_text += f"""
<b>{i}. {pred['event']}</b>
🏆 {pred['league']} | 🕒 {pred['match_time']}
🎯 <b>Palpite:</b> {pred['prediction']}
📈 <b>Odds:</b> {pred['odds']}
💯 <b>Confiança:</b> {pred['confidence']}%

📊 <b>Análise:</b>
{pred['analysis']}
➖➖➖➖➖➖➖➖➖
"""
    
    predictions_text += f"""
🏆 <b>ESTATÍSTICAS DO DIA:</b>
• Palpites gerados: {len(predictions)}
• Confiança média: {sum(p['confidence'] for p in predictions)//len(predictions)}%
• Odds média: {sum(p['odds'] for p in predictions)/len(predictions):.2f}

💎 <b>PARA MAIS PALPITES:</b>
Torne-se VIP para acessar 10-15 palpites diários com análises detalhadas!

📲 <b>SUPORTE:</b>
Dúvidas? Fale com nosso suporte: @{ADMIN_USERNAME[1:]}

⚠️ <i>Palpites são sugestões. Jogue com responsabilidade.</i>
"""
    
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("💎 TORNAR-SE VIP", callback_data="view_plans_main"),
        types.InlineKeyboardButton("🎯 GERAR CÓDIGO", callback_data="generate_code_main")
    )
    
    bot.send_message(
        message.chat.id,
        predictions_text,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(commands=['perfil'])
def profile_command(message):
    user_id = message.from_user.id
    
    cursor.execute('''
        SELECT username, full_name, is_vip, vip_type, vip_until, 
               daily_codes_used, daily_codes_limit, total_codes_created,
               balance, total_spent, total_won, referral_count,
               referral_earnings, created_at
        FROM users WHERE user_id = ?
    ''', (user_id,))
    
    user = cursor.fetchone()
    
    if not user:
        bot.send_message(message.chat.id, "❌ Usuário não encontrado!")
        return
    
    (username, full_name, is_vip, vip_type, vip_until, daily_used, 
     daily_limit, total_codes, balance, total_spent, total_won, 
     referral_count, referral_earnings, created_at) = user
    
    # Calcular estatísticas
    cursor.execute('SELECT COUNT(*) FROM codes WHERE user_id = ? AND is_winner = 1', (user_id,))
    wins = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM codes WHERE user_id = ?', (user_id,))
    total_bets = cursor.fetchone()[0]
    
    win_rate = (wins / total_bets * 100) if total_bets > 0 else 0
    
    profile_text = f"""
👤 <b>MEU PERFIL COMPLETO</b>

📛 <b>Nome:</b> {full_name}
👤 <b>Usuário:</b> @{username if username else 'Não definido'}
🆔 <b>ID:</b> <code>{user_id}</code>

💎 <b>STATUS VIP:</b> {'SIM 🎖️' if is_vip else 'NÃO ⭐'}
📅 <b>Plano:</b> {vip_type if vip_type else 'Grátis'}
⏰ <b>Válido até:</b> {vip_until[:10] if vip_until else 'N/A'}

🎯 <b>ESTATÍSTICAS DE APOSTAS:</b>
🔢 <b>Códigos hoje:</b> {daily_used}/{daily_limit}
📊 <b>Códigos total:</b> {total_codes}
🏆 <b>Vitórias:</b> {wins}
📈 <b>Taxa acerto:</b> {win_rate:.1f}%

💰 <b>FINANCEIRO:</b>
💵 <b>Saldo:</b> {balance:.2f}MT
💸 <b>Total gasto:</b> {total_spent:.2f}MT
🎁 <b>Total ganho:</b> {total_won:.2f}MT
📈 <b>Lucro líquido:</b> {(total_won - total_spent):.2f}MT

👥 <b>PROGRAMA DE INDICAÇÕES:</b>
📋 <b>Código:</b> <code>REF{user_id:06d}</code>
👤 <b>Indicados:</b> {referral_count}
💰 <b>Ganhos indicações:</b> {referral_earnings:.2f}MT

📅 <b>CADASTRO:</b> {created_at[:10] if created_at else 'N/A'}

💡 <b>DICAS:</b>
• Compartilhe seu código de indicação
• Torne-se VIP para mais códigos
• Consulte nosso suporte para dúvidas
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💎 TORNAR-SE VIP", callback_data="view_plans_main"),
        types.InlineKeyboardButton("📤 COMPARTILHAR CÓDIGO", callback_data="share_referral")
    )
    markup.add(
        types.InlineKeyboardButton("📊 HISTÓRICO", callback_data="my_history"),
        types.InlineKeyboardButton("🔄 ATUALIZAR", callback_data="refresh_profile")
    )
    
    bot.send_message(
        message.chat.id,
        profile_text,
        reply_markup=markup,
        parse_mode='HTML'
    )

@bot.message_handler(commands=['admin'])
def admin_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id, "❌ Acesso restrito ao administrador!")
        return
    
    admin_text = f"""
👑 <b>PAINEL ADMINISTRATIVO - BET MASTER PRO</b>

👋 <b>Bem-vindo, Ailton!</b>
📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

📊 <b>ESTATÍSTICAS GERAIS:</b>
• Total usuários: {get_total_users():,}
• Usuários VIP: {get_vip_users_count():,}
• Novos hoje: {get_today_users():,}
• Ativos hoje: {get_active_today():,}
• Códigos gerados: {get_total_codes():,}
• Receita total: {get_total_revenue():,.2f}MT

💰 <b>RECEITA POR PLANO:</b>
• Diário: {get_plan_revenue('daily'):,.2f}MT
• Semanal: {get_plan_revenue('weekly'):,.2f}MT
• Mensal: {get_plan_revenue('monthly'):,.2f}MT
• Premium: {get_plan_revenue('premium'):,.2f}MT

📈 <b>HOJE ({datetime.now().strftime('%d/%m')}):</b>
• Novos usuários: {get_today_users()}
• Códigos gerados: {get_today_codes()}
• Pagamentos: {get_today_payments():,.2f}MT
• VIPs ativados: {get_today_vip_activations()}

🚨 <b>ALERTAS:</b>
• VIPs a expirar hoje: {get_expiring_vips_today()}
• Pagamentos pendentes: {get_pending_payments()}
• Tickets abertos: {get_open_tickets()}

⚙️ <b>FERRAMENTAS ADMIN:</b>
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Primeira linha
    markup.add(
        types.InlineKeyboardButton("📊 ESTATÍSTICAS DETALHADAS", callback_data="admin_stats_detailed"),
        types.InlineKeyboardButton("👤 GERENCIAR USUÁRIOS", callback_data="admin_manage_users")
    )
    
    # Segunda linha
    markup.add(
        types.InlineKeyboardButton("💰 GERENCIAR PAGAMENTOS", callback_data="admin_manage_payments"),
        types.InlineKeyboardButton("🎫 VER TODOS CÓDIGOS", callback_data="admin_view_codes")
    )
    
    # Terceira linha
    markup.add(
        types.InlineKeyboardButton("⚡ ATIVAR VIP MANUAL", callback_data="admin_activate_vip"),
        types.InlineKeyboardButton("📢 ENVIAR BROADCAST", callback_data="admin_broadcast")
    )
    
    # Quarta linha
    markup.add(
        types.InlineKeyboardButton("📞 TICKETS SUPORTE", callback_data="admin_support_tickets"),
        types.InlineKeyboardButton("⚙️ CONFIGURAÇÕES", callback_data="admin_settings")
    )
    
    # Quinta linha - Ações rápidas
    markup.add(
        types.InlineKeyboardButton("🔄 ATUALIZAR DADOS", callback_data="admin_refresh"),
        types.InlineKeyboardButton("📤 EXPORTAR DADOS", callback_data="admin_export")
    )
    
    bot.send_message(
        message.chat.id,
        admin_text,
        reply_markup=markup,
        parse_mode='HTML'
    )

# ================= COMANDOS ADMIN AVANÇADOS =================
@bot.message_handler(commands=['vipmanual'])
def vip_manual_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    msg = bot.send_message(
        message.chat.id,
        "👑 <b>ATIVAÇÃO MANUAL DE VIP</b>\n\n"
        "Digite o ID do usuário para ativar VIP:",
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, process_vip_manual)

def process_vip_manual(message):
    try:
        user_id = int(message.text.strip())
        
        # Verificar se usuário existe
        cursor.execute('SELECT username FROM users WHERE user_id = ?', (user_id,))
        user = cursor.fetchone()
        
        if not user:
            bot.send_message(message.chat.id, "❌ Usuário não encontrado!")
            return
        
        username = user[0]
        
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for plan_id, plan in PRECOS.items():
            markup.add(
                types.InlineKeyboardButton(
                    f"{plan['nome']} - {plan['preco']}MT",
                    callback_data=f"admin_vip_manual_{plan_id}_{user_id}"
                )
            )
        
        markup.add(types.InlineKeyboardButton("❌ CANCELAR", callback_data="admin_cancel"))
        
        bot.send_message(
            message.chat.id,
            f"👤 <b>Usuário:</b> @{username if username else 'Sem username'}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n\n"
            f"Escolha o plano VIP para ativar:",
            reply_markup=markup,
            parse_mode='HTML'
        )
        
    except ValueError:
        bot.send_message(message.chat.id, "❌ ID inválido! Digite apenas números.")

@bot.message_handler(commands=['estatisticas'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    stats_text = generate_detailed_stats()
    bot.send_message(message.chat.id, stats_text, parse_mode='HTML')

@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    
    msg = bot.send_message(
        message.chat.id,
        "📢 <b>ENVIO DE BROADCAST</b>\n\n"
        "Digite a mensagem que deseja enviar a todos os usuários:",
        parse_mode='HTML'
    )
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    broadcast_message = message.text
    
    # Confirmar broadcast
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("✅ CONFIRMAR ENVIO", callback_data=f"confirm_broadcast_{hashlib.md5(broadcast_message.encode()).hexdigest()[:8]}"),
        types.InlineKeyboardButton("❌ CANCELAR", callback_data="cancel_broadcast")
    )
    
    bot.send_message(
        message.chat.id,
        f"📢 <b>CONFIRMAR BROADCAST</b>\n\n"
        f"<b>Mensagem:</b>\n{broadcast_message}\n\n"
        f"⚠️ Esta mensagem será enviada para todos os {get_total_users()} usuários.",
        reply_markup=markup,
        parse_mode='HTML'
    )

# ================= FUNÇÕES DE SUPORTE =================
def get_total_users():
    cursor.execute('SELECT COUNT(*) FROM users')
    return cursor.fetchone()[0]

def get_vip_users_count():
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_vip = 1')
    return cursor.fetchone()[0]

def get_total_codes():
    cursor.execute('SELECT COUNT(*) FROM codes')
    return cursor.fetchone()[0]

def get_total_revenue():
    cursor.execute('SELECT SUM(amount) FROM payments WHERE status = "approved"')
    result = cursor.fetchone()[0]
    return float(result) if result else 0.00

def get_today_users():
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?', (today,))
    return cursor.fetchone()[0]

def get_today_codes():
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM codes WHERE DATE(created_at) = ?', (today,))
    return cursor.fetchone()[0]

def get_today_payments():
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT SUM(amount) FROM payments WHERE DATE(created_at) = ? AND status = "approved"', (today,))
    result = cursor.fetchone()[0]
    return float(result) if result else 0.00

def get_plan_revenue(plan_type):
    cursor.execute('SELECT SUM(amount) FROM payments WHERE plan_type = ? AND status = "approved"', (plan_type,))
    result = cursor.fetchone()[0]
    return float(result) if result else 0.00

def get_active_today():
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(last_active) = ?', (today,))
    return cursor.fetchone()[0]

def get_daily_codes_used(user_id):
    cursor.execute('SELECT daily_codes_used FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def get_user_total_codes(user_id):
    cursor.execute('SELECT total_codes_created FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    return result[0] if result else 0

def get_today_vip_activations():
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM payments WHERE DATE(approved_at) = ? AND status = "approved"', (today,))
    return cursor.fetchone()[0]

def get_expiring_vips_today():
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(vip_until) = ? AND is_vip = 1', (today,))
    return cursor.fetchone()[0]

def get_pending_payments():
    cursor.execute('SELECT COUNT(*) FROM payments WHERE status = "pending"')
    return cursor.fetchone()[0]

def get_open_tickets():
    cursor.execute('SELECT COUNT(*) FROM support_tickets WHERE status = "open"')
    return cursor.fetchone()[0]

def generate_detailed_stats():
    """Gera estatísticas detalhadas para admin"""
    
    # Obter dados
    total_users = get_total_users()
    vip_users = get_vip_users_count()
    total_revenue = get_total_revenue()
    today_revenue = get_today_payments()
    
    # Calcular crescimento
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    cursor.execute('SELECT COUNT(*) FROM users WHERE DATE(created_at) = ?', (yesterday,))
    yesterday_users = cursor.fetchone()[0]
    
    growth = ((get_today_users() - yesterday_users) / yesterday_users * 100) if yesterday_users > 0 else 0
    
    # Top usuários
    cursor.execute('''
        SELECT username, total_codes_created, total_spent 
        FROM users 
        ORDER BY total_spent DESC 
        LIMIT 5
    ''')
    
    top_users = cursor.fetchall()
    
    # Últimos pagamentos
    cursor.execute('''
        SELECT u.username, p.amount, p.plan_type, p.created_at 
        FROM payments p
        JOIN users u ON p.user_id = u.user_id
        WHERE p.status = "approved"
        ORDER BY p.payment_id DESC 
        LIMIT 5
    ''')
    
    recent_payments = cursor.fetchall()
    
    stats_text = f"""
📈 <b>ESTATÍSTICAS DETALHADAS</b>
📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}

👥 <b>USUÁRIOS:</b>
• Total: {total_users:,}
• VIPs: {vip_users:,} ({vip_users/total_users*100:.1f}%)
• Grátis: {total_users - vip_users:,}
• Novos hoje: {get_today_users():,}
• Crescimento: {growth:+.1f}%

💰 <b>FINANCEIRO:</b>
• Receita total: {total_revenue:,.2f}MT
• Receita hoje: {today_revenue:,.2f}MT
• Média por usuário: {total_revenue/total_users if total_users > 0 else 0:,.2f}MT

📊 <b>POR PLANO:</b>
• Diário: {get_plan_revenue('daily'):,.2f}MT
• Semanal: {get_plan_revenue('weekly'):,.2f}MT
• Mensal: {get_plan_revenue('monthly'):,.2f}MT
• Premium: {get_plan_revenue('premium'):,.2f}MT

🎫 <b>CÓDIGOS:</b>
• Total: {get_total_codes():,}
• Hoje: {get_today_codes():,}
• Média por usuário: {get_total_codes()/total_users if total_users > 0 else 0:.1f}

🏆 <b>TOP 5 USUÁRIOS (GASTOS):</b>
"""
    
    for i, (username, codes, spent) in enumerate(top_users, 1):
        stats_text += f"{i}. @{username if username else 'N/A'}: {spent:,.2f}MT ({codes} códigos)\n"
    
    stats_text += f"\n💸 <b>ÚLTIMOS 5 PAGAMENTOS:</b>\n"
    
    for username, amount, plan_type, created_at in recent_payments:
        stats_text += f"• @{username if username else 'N/A'}: {amount}MT ({plan_type}) - {created_at[:10]}\n"
    
    return stats_text

def log_admin_action(admin_id: int, action: str, target_user_id: int, details: str):
    """Registra ação administrativa"""
    cursor.execute('''
        INSERT INTO admin_logs (admin_id, action, target_user_id, details, created_at)
        VALUES (?, ?, ?, ?, ?)
    ''', (admin_id, action, target_user_id, details, datetime.now()))
    conn.commit()

# ================= CALLBACK HANDLERS =================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data
    
    try:
        if data == "generate_code_main":
            generate_code_command(call.message)
        
        elif data == "view_plans_main":
            vip_command(call.message)
        
        elif data == "daily_predictions":
            predictions_command(call.message)
        
        elif data == "my_profile_main":
            profile_command(call.message)
        
        elif data == "payment_methods":
            payment_methods_text = f"""
💰 <b>FORMAS DE PAGAMENTO DISPONÍVEIS</b>

📱 <b>PARA MOÇAMBIQUE:</b>
1. <b>EMOLA:</b> {PAYMENT_INFO['emola']}
2. <b>M-PESA:</b> {PAYMENT_INFO['mpesa']}

🌍 <b>INTERNACIONAL:</b>
3. <b>PAYPAL:</b> {PAYMENT_INFO['paypal']}

📞 <b>CONTATOS:</b>
• Telegram: {ADMIN_USERNAME}
• WhatsApp: {SUPPORT_WHATSAPP}
• Email: {ADMIN_EMAIL}

⚡ <b>PROCEDIMENTO:</b>
1. Escolha seu plano VIP (/vip)
2. Faça o pagamento via método escolhido
3. Envie comprovante para {ADMIN_USERNAME}
4. Aguarde ativação (5-15 minutos)
5. Receba confirmação automática

⏱️ <b>HORÁRIO DE ATENDIMENTO:</b>
• Seg-Sex: 08:00-22:00
• Sáb-Dom: 09:00-20:00

🎁 <b>GARANTIA:</b>
• Ativação em até 15 minutos
• Suporte 24/7 para VIPs
• Reembolso em caso de erro
"""
            bot.send_message(call.message.chat.id, payment_methods_text, parse_mode='HTML')
        
        elif data == "contact_support":
            support_text = f"""
📞 <b>SUPORTE BET MASTER PRO</b>

💬 <b>FALE CONOSCO:</b>
• Telegram: {ADMIN_USERNAME}
• WhatsApp: {SUPPORT_WHATSAPP}
• Email: {ADMIN_EMAIL}

🕒 <b>HORÁRIO:</b>
• Segunda a Sexta: 08:00 - 22:00
• Sábado e Domingo: 09:00 - 20:00

🔧 <b>ASSUNTOS ATENDIDOS:</b>
• Ativação de VIP
• Problemas com códigos
• Dúvidas sobre pagamento
• Sugestões e feedback
• Problemas técnicos

⚡ <b>PARA ATENDIMENTO RÁPIDO:</b>
1. Digite /start no bot
2. Selecione "📞 SUPORTE 24/7"
3. Aguarde resposta (máx. 15 minutos)

💎 <b>VIPs TEM PRIORIDADE!</b>
            """
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("💬 TELEGRAM", url=f"https://t.me/{ADMIN_USERNAME[1:]}"),
                types.InlineKeyboardButton("📱 WHATSAPP", url=f"https://wa.me/{SUPPORT_WHATSAPP.replace('+', '')}")
            )
            bot.send_message(call.message.chat.id, support_text, reply_markup=markup, parse_mode='HTML')
        
        elif data == "admin_panel":
            if user_id == ADMIN_ID:
                admin_command(call.message)
            else:
                bot.answer_callback_query(call.id, "❌ Acesso restrito!", show_alert=True)
        
        elif data.startswith("buy_plan_"):
            plan_id = data.replace("buy_plan_", "")
            plan = PRECOS.get(plan_id)
            
            if plan:
                buy_text = f"""
🛒 <b>COMPRAR {plan['nome'].upper()}</b>

📋 <b>DETALHES DO PLANO:</b>
• Nome: {plan['nome']}
• Preço: {plan['preco']}MT
• Códigos/dia: {plan['codigos_dia']}
• Validade: {plan['dias']} dia(s)

📱 <b>PARA COMPRAR:</b>
1. Faça pagamento de {plan['preco']}MT para:
   • Emola: {PAYMENT_INFO['emola']}
   • M-Pesa: {PAYMENT_INFO['mpesa']}
   • PayPal: {PAYMENT_INFO['paypal']}

2. Envie comprovante para:
   • Telegram: {ADMIN_USERNAME}
   • WhatsApp: {SUPPORT_WHATSAPP}

3. Informe seu ID: <code>{user_id}</code>

4. Aguarde ativação (5-15 minutos)

🎁 <b>BÔNUS:</b> Ativação em até 15 minutos!
                """
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("📲 ENVIAR COMPROVANTE", url=f"https://t.me/{ADMIN_USERNAME[1:]}"),
                    types.InlineKeyboardButton("💬 WHATSAPP", url=f"https://wa.me/{SUPPORT_WHATSAPP.replace('+', '')}")
                )
                markup.add(
                    types.InlineKeyboardButton("🔙 VOLTAR", callback_data="view_plans_main")
                )
                
                bot.send_message(call.message.chat.id, buy_text, reply_markup=markup, parse_mode='HTML')
        
        elif data.startswith("admin_vip_manual_"):
            if user_id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Acesso negado!", show_alert=True)
                return
            
            # Formato: admin_vip_manual_{plan_id}_{user_id}
            parts = data.split("_")
            plan_id = parts[3]
            target_user_id = int(parts[4])
            
            # Ativar VIP
            success = VIPSystem.activate_vip(target_user_id, plan_id, user_id)
            
            if success:
                bot.answer_callback_query(call.id, "✅ VIP ativado com sucesso!", show_alert=True)
                
                # Obter nome do usuário
                cursor.execute('SELECT username FROM users WHERE user_id = ?', (target_user_id,))
                target_username = cursor.fetchone()
                target_username = target_username[0] if target_username else "N/A"
                
                # Enviar confirmação
                bot.send_message(
                    call.message.chat.id,
                    f"✅ <b>VIP ATIVADO!</b>\n\n"
                    f"👤 Usuário: @{target_username}\n"
                    f"🆔 ID: <code>{target_user_id}</code>\n"
                    f"💎 Plano: {PRECOS[plan_id]['nome']}\n"
                    f"💰 Valor: {PRECOS[plan_id]['preco']}MT\n"
                    f"⏰ Ativado em: {datetime.now().strftime('%H:%M:%S')}",
                    parse_mode='HTML'
                )
            else:
                bot.answer_callback_query(call.id, "❌ Erro ao ativar VIP!", show_alert=True)
        
        elif data == "admin_stats_detailed":
            if user_id != ADMIN_ID:
                return
            
            stats_text = generate_detailed_stats()
            bot.send_message(call.message.chat.id, stats_text, parse_mode='HTML')
        
        elif data.startswith("confirm_broadcast_"):
            if user_id != ADMIN_ID:
                return
            
            # Obter mensagem original (simplificado)
            msg = call.message.text
            lines = msg.split('\n')
            broadcast_msg = '\n'.join(lines[4:-2])  # Extrair mensagem
            
            # Enviar para todos usuários
            cursor.execute('SELECT user_id FROM users')
            users = cursor.fetchall()
            
            sent = 0
            failed = 0
            
            for (uid,) in users:
                try:
                    bot.send_message(uid, f"📢 <b>COMUNICADO IMPORTANTE</b>\n\n{broadcast_msg}", parse_mode='HTML')
                    sent += 1
                except:
                    failed += 1
                time.sleep(0.05)  # Evitar rate limit
            
            bot.send_message(
                call.message.chat.id,
                f"📊 <b>BROADCAST CONCLUÍDO</b>\n\n"
                f"✅ Enviados: {sent}\n"
                f"❌ Falhas: {failed}\n"
                f"📅 {datetime.now().strftime('%H:%M:%S')}",
                parse_mode='HTML'
            )
        
        # Adicionar mais handlers conforme necessário...
        
        else:
            bot.answer_callback_query(call.id, "⚡ Comando processado!")
    
    except Exception as e:
        logger.error(f"Erro no callback: {e}")
        bot.answer_callback_query(call.id, "❌ Erro ao processar comando!", show_alert=True)

# ================= FUNÇÕES DE MANUTENÇÃO =================
def reset_daily_counts():
    """Reseta contadores diários dos usuários"""
    cursor.execute('UPDATE users SET daily_codes_used = 0 WHERE is_vip = 0')
    cursor.execute('UPDATE users SET daily_codes_used = 0 WHERE is_vip = 1 AND vip_until < ?', 
                  (datetime.now().strftime('%Y-%m-%d %H:%M:%S'),))
    conn.commit()
    logger.info("Contadores diários resetados")

def check_expired_vips():
    """Verifica e remove VIPs expirados"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute('''
        SELECT user_id, username FROM users 
        WHERE vip_until < ? AND is_vip = 1
    ''', (now,))
    
    expired_users = cursor.fetchall()
    
    for user_id, username in expired_users:
        cursor.execute('''
            UPDATE users 
            SET is_vip = 0, vip_type = NULL, vip_until = NULL, daily_codes_limit = 2
            WHERE user_id = ?
        ''', (user_id,))
        
        # Notificar usuário
        try:
            bot.send_message(
                user_id,
                "⚠️ <b>SEU VIP EXPIROU!</b>\n\n"
                "Seu plano VIP chegou ao fim. Você voltou para o plano grátis (2 códigos/dia).\n\n"
                "Para renovar ou comprar novo plano, use /vip\n\n"
                "Obrigado por ser nosso cliente! 🎯",
                parse_mode='HTML'
            )
        except:
            pass
    
    conn.commit()
    
    if expired_users:
        logger.info(f"{len(expired_users)} VIPs expirados removidos")

def backup_database():
    """Cria backup do banco de dados"""
    try:
        backup_name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        with open('betmaster_v2.db', 'rb') as src, open(backup_name, 'wb') as dst:
            dst.write(src.read())
        logger.info(f"Backup criado: {backup_name}")
    except Exception as e:
        logger.error(f"Erro no backup: {e}")

# Agendar tarefas
schedule.every().day.at("00:00").do(reset_daily_counts)
schedule.every().hour.do(check_expired_vips)
schedule.every().day.at("02:00").do(backup_database)

def run_scheduler():
    """Executa o scheduler em thread separada"""
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Verificar a cada minuto
        except Exception as e:
            logger.error(f"Erro no scheduler: {e}")
            time.sleep(300)

# ================= INICIAR BOT =================
if __name__ == '__main__':
    print("""
    ╔══════════════════════════════════════════╗
    ║      🏆 BET MASTER PRO BOT v2.0         ║
    ║      Configurado com seus dados!        ║
    ╚══════════════════════════════════════════╝
    
    👑 Admin: Ailton Armindo
    🆔 ID: 5125563829
    📧 Email: ayltonanna@gmail.com
    📱 WhatsApp: +258 84 856 8229
    
    💰 Formas de pagamento configuradas:
    • Emola: 870612404 - Ailton Armindo
    • M-Pesa: 848568229 - Ailton Armindo
    • PayPal: ayltonanna@gmail.com
    
    ⚡ Iniciando sistema...
    """)
    
    # Iniciar scheduler em thread separada
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("✅ Scheduler iniciado")
    
    # Iniciar bot
    logger.info(f"🤖 Iniciando bot: {BOT_USERNAME}")
    
    try:
        bot.polling(none_stop=True, interval=1, timeout=30)
    except Exception as e:
        logger.error(f"❌ Erro no bot: {e}")
    finally:
        conn.close()
        logger.info("📴 Bot encerrado")