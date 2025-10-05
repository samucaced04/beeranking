from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import requests
from datetime import datetime, timedelta
import os
import re

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta_aqui'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Modelos do Banco de Dados
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    beecrowd_id = db.Column(db.Integer)
    # Adicione esta linha para relacionamento
    activities = db.relationship('Activity', backref='user', lazy=True)

class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    problems_solved = db.Column(db.Integer, default=0)
    date = db.Column(db.Date, default=datetime.utcnow)
    week_number = db.Column(db.Integer)

class Friend(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    friend_beecrowd_id = db.Column(db.Integer, nullable=False)

# Função para pegar dados do BeeCrownd - MELHORADA
def get_beecrowd_data(beecrowd_id):
    try:
        print(f"🌐 Acessando BeeCrowd para ID: {beecrowd_id}")
        url = f"https://www.beecrowd.com.br/judge/pt/profile/{beecrowd_id}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"📡 Status da resposta: {response.status_code}")
        
        if response.status_code == 200:
            content = response.text
            print(f"📄 Tamanho da página: {len(content)} caracteres")
            
            # Padrões melhorados
            patterns = [
                r'Resolvido:</div>\s*<div[^>]*>(\d+)',
                r'Solved:</div>\s*<div[^>]*>(\d+)',
                r'resolvido[^\d]*(\d+)',
                r'solved[^\d]*(\d+)',
                r'Problems.*?(\d+)'
            ]
            
            for i, pattern in enumerate(patterns):
                matches = re.search(pattern, content, re.IGNORECASE)
                if matches:
                    solved = int(matches.group(1))
                    print(f"✅ Padrão {i+1} encontrado: {solved} problemas")
                    return solved
            
            print("❌ Nenhum padrão encontrado na página")
            return 0
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return 0
    except Exception as e:
        print(f"💥 Erro exception: {e}")
        return 0

# Rotas
@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username, password=password).first()
        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login realizado com sucesso!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        beecrowd_id = request.form['beecrowd_id']
        
        if User.query.filter_by(username=username).first():
            flash('Usuário já existe!', 'error')
        else:
            new_user = User(username=username, password=password, beecrowd_id=beecrowd_id)
            db.session.add(new_user)
            db.session.commit()
            flash('Conta criada com sucesso! Faça login.', 'success')
            return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if not user:
        session.clear()
        flash('Sessão expirada. Faça login novamente.', 'error')
        return redirect(url_for('login'))
    
    current_week = datetime.now().isocalendar()[1]
    today_activity = Activity.query.filter_by(
        user_id=user.id, 
        date=datetime.now().date()
    ).first()
    
    if not today_activity:
        problems_solved = get_beecrowd_data(user.beecrowd_id)
        
        # DEBUG ADICIONADO AQUI ↓
        print(f"🔍 DEBUG: Tentando pegar dados do BeeCrowd ID {user.beecrowd_id}")
        print(f"🔍 DEBUG: Problemas encontrados: {problems_solved}")
        
        new_activity = Activity(
            user_id=user.id, 
            problems_solved=problems_solved,
            week_number=current_week
        )
        db.session.add(new_activity)
        db.session.commit()
    
    # Ranking da semana - CÁLCULO CORRIGIDO ↓
    users = User.query.all()
    ranking_data = []
    
    for user_obj in users:
        # Soma TODAS as atividades da semana atual - MÉTODO CORRIGIDO
        weekly_activities = Activity.query.filter_by(
            user_id=user_obj.id, 
            week_number=current_week
        ).all()
        
        total_solved = sum(activity.problems_solved for activity in weekly_activities)
        
        ranking_data.append({
            'username': user_obj.username,
            'problems_solved': total_solved,
            'beecrowd_id': user_obj.beecrowd_id
        })
    
    ranking_data.sort(key=lambda x: x['problems_solved'], reverse=True)
    
    return render_template('dashboard.html', 
                         user=user, 
                         ranking=ranking_data[:10], 
                         current_week=current_week)

@app.route('/sync_beecrowd')
def sync_beecrowd():
    """Rota para sincronizar manualmente com o BeeCrowd"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    problems_solved = get_beecrowd_data(user.beecrowd_id)
    
    if problems_solved > 0:
        # Atualiza ou cria atividade de hoje
        today_activity = Activity.query.filter_by(
            user_id=user.id, 
            date=datetime.now().date()
        ).first()
        
        if today_activity:
            today_activity.problems_solved = problems_solved
        else:
            new_activity = Activity(
                user_id=user.id,
                problems_solved=problems_solved,
                date=datetime.now().date(),
                week_number=datetime.now().isocalendar()[1]
            )
            db.session.add(new_activity)
        
        db.session.commit()
        flash(f'✅ Sincronizado! {problems_solved} problemas encontrados no BeeCrowd.', 'success')
    else:
        flash('❌ Não foi possível pegar os dados do BeeCrowd. Use o modo manual.', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/add_problems', methods=['POST'])
def add_problems():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    try:
        problems_to_add = int(request.form['problems_solved'])
        current_week = datetime.now().isocalendar()[1]
        today = datetime.now().date()
        
        # DEBUG ADICIONADO
        print(f"💾 Adicionando {problems_to_add} problemas para o usuário {session['user_id']} na data {today}")
        
        # Busca atividade de hoje
        today_activity = Activity.query.filter_by(
            user_id=session['user_id'],
            date=today
        ).first()
        
        if today_activity:
            # Se já tem atividade hoje, ADICIONA aos problemas existentes
            new_total = today_activity.problems_solved + problems_to_add
            print(f"📝 Somando: {today_activity.problems_solved} + {problems_to_add} = {new_total}")
            today_activity.problems_solved = new_total
        else:
            # Se não tem atividade hoje, cria nova
            print(f"🆕 Criando nova atividade: {problems_to_add} problemas")
            today_activity = Activity(
                user_id=session['user_id'],
                problems_solved=problems_to_add,
                date=today,
                week_number=current_week
            )
            db.session.add(today_activity)
        
        db.session.commit()
        print("✅ Banco de dados salvo com sucesso!")
        flash(f'✅ {problems_to_add} problemas adicionados com sucesso! Total de hoje: {today_activity.problems_solved}', 'success')
        
    except ValueError:
        flash('❌ Por favor, digite um número válido', 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/add_friend', methods=['POST'])
def add_friend():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    friend_id = request.form['friend_id']
    
    new_friend = Friend(
        user_id=session['user_id'],
        friend_beecrowd_id=friend_id
    )
    db.session.add(new_friend)
    db.session.commit()
    
    flash('Amigo adicionado com sucesso!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/progresso')
def progresso():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    if not user:
        session.clear()
        flash('Sessão expirada. Faça login novamente.', 'error')
        return redirect(url_for('login'))
    
    # Pegar dados das últimas 6 semanas
    current_week = datetime.now().isocalendar()[1]
    current_year = datetime.now().year
    weekly_data = []
    
    for week_offset in range(6):
        week_number = current_week - week_offset
        year = current_year
        
        # Ajuste para semanas do ano anterior
        if week_number <= 0:
            week_number += 52
            year -= 1
        
        weekly_activities = Activity.query.filter_by(
            user_id=user.id, 
            week_number=week_number
        ).all()
        
        total_solved = sum(activity.problems_solved for activity in weekly_activities)
        
        weekly_data.append({
            'week': week_number,
            'year': year,
            'problems_solved': total_solved,
            'label': f"Semana {week_number}"
        })
    
    # Ordenar da mais antiga para a mais recente
    weekly_data.reverse()
    
    # Calcular estatísticas
    problems_list = [data['problems_solved'] for data in weekly_data]
    stats = {
        'total': sum(problems_list),
        'average': sum(problems_list) / len(problems_list) if problems_list else 0,
        'best_week': max(problems_list) if problems_list else 0,
        'current_week': current_week
    }
    
    return render_template('progresso.html', 
                         user=user, 
                         weekly_data=weekly_data,
                         stats=stats)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logout realizado com sucesso!', 'success')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
