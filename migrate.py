from app import app, db

def migrate():
    with app.app_context():
        print("마이그레이션이 완료되었습니다.")

if __name__ == '__main__':
    migrate() 