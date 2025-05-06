from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'mysql+pymysql://root:1234@localhost/accountee')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
db = SQLAlchemy(app)

# 데이터베이스 모델
class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=True)  # 비밀번호는 선택사항
    use_password = db.Column(db.Boolean, default=False)  # 비밀번호 사용 여부
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    transactions = db.relationship('Transaction', backref='project', lazy=True)
    participants = db.relationship('Participant', backref='project', lazy=True)

class Participant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    shares = db.relationship('Share', backref='participant', lazy=True)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(200))
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    category = db.Column(db.String(50))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    shares = db.relationship('Share', backref='transaction', lazy=True)

class Share(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transaction.id'), nullable=False)
    participant_id = db.Column(db.Integer, db.ForeignKey('participant.id'), nullable=False)

def validate_amount(amount_str):
    try:
        amount = float(amount_str)
        if amount <= 0:
            return False, "금액은 0보다 커야 합니다."
        return True, amount
    except ValueError:
        return False, "올바른 금액을 입력해주세요."

def validate_name(name):
    if not name or len(name.strip()) == 0:
        return False, "이름을 입력해주세요."
    if len(name) > 50:
        return False, "이름은 50자 이하여야 합니다."
    if not re.match(r'^[가-힣a-zA-Z0-9\s]+$', name):
        return False, "이름은 한글, 영문, 숫자만 사용 가능합니다."
    return True, name.strip()

@app.route('/', methods=['GET'])
def index():
    projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template('index.html', projects=projects)

@app.route('/project/<int:project_id>', methods=['GET', 'POST'])
def project(project_id):
    try:
        project = Project.query.get_or_404(project_id)
        
        # 비밀번호가 필요한 경우
        if project.use_password:
            if request.method == 'POST':
                password = request.form.get('password')
                if not password:
                    flash('비밀번호를 입력해주세요.', 'error')
                    return render_template('project.html', project=project, show_password_form=True)
                
                if not check_password_hash(project.password, password):
                    flash('잘못된 비밀번호입니다.', 'error')
                    return render_template('project.html', project=project, show_password_form=True)
                
                return render_template('project.html', project=project)
            else:
                return render_template('project.html', project=project, show_password_form=True)
        
        return render_template('project.html', project=project)
    except Exception as e:
        flash('프로젝트를 불러오는 중 오류가 발생했습니다.', 'error')
        return redirect(url_for('index'))

@app.route('/project/<int:project_id>/edit', methods=['POST'])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    project.name = request.form['project_name']
    db.session.commit()
    flash('프로젝트가 수정되었습니다.', 'success')
    return redirect(url_for('project', project_id=project.id))

@app.route('/project/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    db.session.delete(project)
    db.session.commit()
    flash('프로젝트가 삭제되었습니다.', 'success')
    return redirect(url_for('index'))

@app.route('/project/<int:project_id>/toggle_password', methods=['POST'])
def toggle_password(project_id):
    try:
        project = Project.query.get_or_404(project_id)
        if project.password:
            project.password = None
            project.use_password = False
            flash('비밀번호가 해제되었습니다.', 'success')
        else:
            password = request.form.get('password')
            if not password:
                flash('비밀번호를 입력해주세요.', 'error')
                return redirect(url_for('project', project_id=project.id))
            if len(password) < 4:
                flash('비밀번호는 4자 이상이어야 합니다.', 'error')
                return redirect(url_for('project', project_id=project.id))
            project.password = generate_password_hash(password)
            project.use_password = True
            flash('비밀번호가 설정되었습니다.', 'success')
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash('비밀번호 설정 중 오류가 발생했습니다.', 'error')
    return redirect(url_for('project', project_id=project.id))

@app.route('/project/<int:project_id>/add_participant', methods=['POST'])
def add_participant(project_id):
    project = Project.query.get_or_404(project_id)
    name = request.form['name']
    participant = Participant(name=name, project_id=project.id)
    db.session.add(participant)
    db.session.commit()
    flash('인원이 추가되었습니다.', 'success')
    return redirect(url_for('project', project_id=project.id))

@app.route('/project/<int:project_id>/participant/<int:participant_id>/edit', methods=['POST'])
def edit_participant(project_id, participant_id):
    participant = Participant.query.get_or_404(participant_id)
    participant.name = request.form['name']
    db.session.commit()
    flash('인원 정보가 수정되었습니다.', 'success')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/participant/<int:participant_id>/delete', methods=['POST'])
def delete_participant(project_id, participant_id):
    participant = Participant.query.get_or_404(participant_id)
    db.session.delete(participant)
    db.session.commit()
    flash('인원이 삭제되었습니다.', 'success')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/transaction/<int:transaction_id>/edit', methods=['POST'])
def edit_transaction(project_id, transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    transaction.description = request.form['description']
    transaction.amount = float(request.form['amount'])
    transaction.payer_id = int(request.form['payer_id'])
    transaction.date = datetime.strptime(request.form['date'], '%Y-%m-%d')
    db.session.commit()
    flash('거래가 수정되었습니다.', 'success')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/transaction/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(project_id, transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    db.session.delete(transaction)
    db.session.commit()
    flash('거래가 삭제되었습니다.', 'success')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/create', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        name = request.form['project_name']
        participants = request.form.getlist('participants[]')
        password = request.form.get('password')
        
        project = Project(name=name, password=password)
        db.session.add(project)
        db.session.commit()
        
        for participant_name in participants:
            participant = Participant(name=participant_name, project_id=project.id)
            db.session.add(participant)
        
        db.session.commit()
        flash('프로젝트가 생성되었습니다.', 'success')
        return redirect(url_for('project', project_id=project.id))
    
    return render_template('create_project.html')

@app.route('/statistics/<int:project_id>')
def statistics(project_id):
    project = Project.query.get_or_404(project_id)
    participants = Participant.query.filter_by(project_id=project_id).all()
    
    # 각 참여자의 총 지출 금액
    participant_totals = {}
    for participant in participants:
        total = sum(share.amount for share in participant.shares)
        participant_totals[participant.id] = total
    
    # 카테고리별 총 지출
    category_totals = {}
    transactions = Transaction.query.filter_by(project_id=project_id).all()
    for transaction in transactions:
        category = transaction.category
        if category not in category_totals:
            category_totals[category] = 0
        category_totals[category] += transaction.amount
    
    # 전체 총액
    total_amount = sum(transaction.amount for transaction in transactions)
    
    return render_template('statistics.html',
                         project=project,
                         participants=participants,
                         participant_totals=participant_totals,
                         category_totals=category_totals,
                         total_amount=total_amount)

@app.route('/statistics/<int:project_id>/participant/<int:participant_id>')
def participant_statistics(project_id, participant_id):
    project = Project.query.get_or_404(project_id)
    participant = Participant.query.get_or_404(participant_id)
    
    if participant.project_id != project_id:
        flash('잘못된 접근입니다.')
        return redirect(url_for('statistics', project_id=project_id))
    
    # 해당 참여자의 지출이 포함된 거래 목록
    transactions = Transaction.query.join(Share).filter(
        Share.participant_id == participant_id,
        Transaction.project_id == project_id
    ).order_by(Transaction.date.desc()).all()
    
    # 해당 참여자의 지출 총액
    total_amount = sum(share.amount for share in participant.shares)
    
    # 카테고리별 지출
    category_totals = {}
    for transaction in transactions:
        share = next(share for share in transaction.shares if share.participant_id == participant_id)
        if transaction.category not in category_totals:
            category_totals[transaction.category] = 0
        category_totals[transaction.category] += share.amount
    
    return render_template('participant_statistics.html',
                         project=project,
                         participant=participant,
                         transactions=transactions,
                         total_amount=total_amount,
                         category_totals=category_totals)

@app.route('/project/<int:project_id>/logout', methods=['POST'])
def logout_project(project_id):
    authenticated_projects = session.get('authenticated_projects', [])
    if project_id in authenticated_projects:
        authenticated_projects.remove(project_id)
        session['authenticated_projects'] = authenticated_projects
    return redirect(url_for('project', project_id=project_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=False)
