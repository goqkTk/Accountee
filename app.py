from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from datetime import datetime
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
csrf = CSRFProtect(app)
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

@app.route('/create_project', methods=['GET', 'POST'])
def create_project():
    if request.method == 'POST':
        project_name = request.form['project_name']
        use_password = 'use_password' in request.form
        password = request.form.get('password', '')
        participants = request.form.getlist('participants[]')
        
        if not participants:
            flash('최소 한 명의 참여자가 필요합니다.')
            return redirect(url_for('create_project'))
        
        if Project.query.filter_by(name=project_name).first():
            flash('이미 존재하는 프로젝트 이름입니다.')
            return redirect(url_for('create_project'))
        
        project = Project(
            name=project_name,
            password=generate_password_hash(password) if use_password else None,
            use_password=use_password
        )
        db.session.add(project)
        db.session.commit()
        
        # 참여자 추가
        for name in participants:
            is_valid, valid_name = validate_name(name)
            if not is_valid:
                flash(valid_name)
                return redirect(url_for('create_project'))
            participant = Participant(name=valid_name, project_id=project.id)
            db.session.add(participant)
        db.session.commit()
        
        return redirect(url_for('project', project_id=project.id))
    
    return render_template('create_project.html')

@app.route('/project/<int:project_id>', methods=['GET', 'POST'])
def project(project_id):
    project = Project.query.get_or_404(project_id)
    
    if project.use_password and request.method == 'POST':
        if not check_password_hash(project.password, request.form['password']):
            flash('비밀번호가 일치하지 않습니다.')
            return redirect(url_for('index'))
    
    transactions = Transaction.query.filter_by(project_id=project.id).order_by(Transaction.date.desc()).all()
    participants = Participant.query.filter_by(project_id=project.id).all()
    
    # 각 참여자의 총 지출 금액 계산
    participant_totals = {}
    for participant in participants:
        total = sum(share.amount for share in participant.shares)                                                                                   
        participant_totals[participant.id] = total
    
    return render_template('project.html', 
                         project=project, 
                         transactions=transactions,
                         participants=participants,
                         participant_totals=participant_totals)

@app.route('/add_participant/<int:project_id>', methods=['POST'])
def add_participant(project_id):
    name = request.form['name']
    is_valid, result = validate_name(name)
    if not is_valid:
        flash(result)
        return redirect(url_for('project', project_id=project_id))
    
    participant = Participant(name=result, project_id=project_id)
    db.session.add(participant)
    db.session.commit()
    flash('참여자가 추가되었습니다!')
    return redirect(url_for('project', project_id=project_id))

@app.route('/add_transaction/<int:project_id>', methods=['POST'])
def add_transaction(project_id):
    project = Project.query.get_or_404(project_id)
    participants = Participant.query.filter_by(project_id=project_id).all()
    
    if not participants:
        flash('거래를 추가하기 전에 먼저 참여자를 추가해주세요.')
        return redirect(url_for('project', project_id=project_id))
    
    description = request.form.get('description', '')
    category = request.form['category']
    split_type = request.form.get('split_type', 'equal')
    
    if split_type == 'equal':
        # 균등 분담
        amount_str = request.form['amount']
        is_valid, amount = validate_amount(amount_str)
        if not is_valid:
            flash(amount)
            return redirect(url_for('project', project_id=project_id))
            
        transaction = Transaction(
            amount=amount,
            description=description,
            category=category,
            project_id=project_id
        )
        db.session.add(transaction)
        db.session.commit()
        
        # 균등 분담 처리
        share_amount = amount / len(participants)
        for participant in participants:
            share = Share(
                amount=share_amount,
                transaction_id=transaction.id,
                participant_id=participant.id
            )
            db.session.add(share)
    else:
        # 개별 분담
        total_amount = 0
        for participant in participants:
            individual_amount_str = request.form.get(f'individual_amount_{participant.id}', '0')
            is_valid, individual_amount = validate_amount(individual_amount_str)
            if not is_valid:
                flash(individual_amount)
                return redirect(url_for('project', project_id=project_id))
            total_amount += individual_amount
        
        # 개별 분담의 경우 총 금액을 개별 금액의 합으로 설정
        transaction = Transaction(
            amount=total_amount,
            description=description,
            category=category,
            project_id=project_id
        )
        db.session.add(transaction)
        db.session.commit()
        
        # 개별 분담 처리
        for participant in participants:
            individual_amount_str = request.form.get(f'individual_amount_{participant.id}', '0')
            is_valid, individual_amount = validate_amount(individual_amount_str)
            if not is_valid:
                flash(individual_amount)
                return redirect(url_for('project', project_id=project_id))
                
            if individual_amount > 0:
                share = Share(
                    amount=individual_amount,
                    transaction_id=transaction.id,
                    participant_id=participant.id
                )
                db.session.add(share)
    
    db.session.commit()
    flash('거래가 성공적으로 추가되었습니다!')
    return redirect(url_for('project', project_id=project_id))

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

@app.route('/project/<int:project_id>/participant/<int:participant_id>/edit', methods=['POST'])
def edit_participant(project_id, participant_id):
    participant = Participant.query.get_or_404(participant_id)
    if participant.project_id != project_id:
        flash('잘못된 접근입니다.')
        return redirect(url_for('project', project_id=project_id))
    
    new_name = request.form['name']
    if not new_name:
        flash('이름을 입력해주세요.')
        return redirect(url_for('project', project_id=project_id))
    
    participant.name = new_name
    db.session.commit()
    flash('인원 이름이 수정되었습니다.')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/participant/<int:participant_id>/delete', methods=['POST'])
def delete_participant(project_id, participant_id):
    participant = Participant.query.get_or_404(participant_id)
    if participant.project_id != project_id:
        flash('잘못된 접근입니다.')
        return redirect(url_for('project', project_id=project_id))
    
    # 참여자의 모든 분담 기록 삭제
    Share.query.filter_by(participant_id=participant_id).delete()
    db.session.delete(participant)
    db.session.commit()
    flash('인원이 삭제되었습니다.')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/delete', methods=['POST'])
def delete_project(project_id):
    project = Project.query.get_or_404(project_id)
    
    # 프로젝트와 관련된 모든 데이터 삭제
    # 먼저 모든 거래의 ID를 가져옴
    transaction_ids = [t.id for t in Transaction.query.filter_by(project_id=project_id).all()]
    
    # Share 테이블에서 해당 거래들과 관련된 데이터 삭제
    if transaction_ids:
        Share.query.filter(Share.transaction_id.in_(transaction_ids)).delete(synchronize_session=False)
    
    # 나머지 데이터 삭제
    Transaction.query.filter_by(project_id=project_id).delete()
    Participant.query.filter_by(project_id=project_id).delete()
    
    db.session.delete(project)
    db.session.commit()
    
    flash('프로젝트가 삭제되었습니다.')
    return redirect(url_for('index'))

@app.route('/project/<int:project_id>/edit', methods=['POST'])
def edit_project(project_id):
    project = Project.query.get_or_404(project_id)
    new_name = request.form['name']
    
    if not new_name:
        flash('프로젝트 이름을 입력해주세요.')
        return redirect(url_for('project', project_id=project_id))
    
    if Project.query.filter(Project.name == new_name, Project.id != project_id).first():
        flash('이미 존재하는 프로젝트 이름입니다.')
        return redirect(url_for('project', project_id=project_id))
    
    project.name = new_name
    db.session.commit()
    flash('프로젝트 이름이 변경되었습니다.')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/transaction/<int:transaction_id>/edit', methods=['POST'])
def edit_transaction(project_id, transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.project_id != project_id:
        flash('잘못된 접근입니다.')
        return redirect(url_for('project', project_id=project_id))
    
    category = request.form.get('category')
    description = request.form.get('description', '')
    
    if not category:
        flash('카테고리는 필수 입력 항목입니다.')
        return redirect(url_for('project', project_id=project_id))
    
    transaction.category = category
    transaction.description = description
    
    db.session.commit()
    flash('지출이 수정되었습니다.')
    return redirect(url_for('project', project_id=project_id))

@app.route('/project/<int:project_id>/transaction/<int:transaction_id>/delete', methods=['POST'])
def delete_transaction(project_id, transaction_id):
    transaction = Transaction.query.get_or_404(transaction_id)
    if transaction.project_id != project_id:
        flash('잘못된 접근입니다.')
        return redirect(url_for('project', project_id=project_id))
    
    # Share 테이블의 관련 항목도 함께 삭제
    Share.query.filter_by(transaction_id=transaction_id).delete()
    db.session.delete(transaction)
    db.session.commit()
    
    flash('지출이 삭제되었습니다.')
    return redirect(url_for('project', project_id=project_id))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=False)