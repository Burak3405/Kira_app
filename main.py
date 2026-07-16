import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Veritabanı yapılandırması
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


class Mulkler(db.Model):
    __tablename__ = 'mulkler'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    tur = db.Column(db.String(50), nullable=False)
    adres = db.Column(db.Text)
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.now)
    
    sozlesmeler = db.relationship('Sozlesmeler', backref='mulk', lazy=True)

class Kiracilar(db.Model):
    __tablename__ = 'kiracilar'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(50), nullable=False)
    soyad = db.Column(db.String(50), nullable=False)
    telefon = db.Column(db.String(20))
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.now)
    
    sozlesmeler = db.relationship('Sozlesmeler', backref='kiraci', lazy=True)

class Sozlesmeler(db.Model):
    __tablename__ = 'sozlesmeler'
    id = db.Column(db.Integer, primary_key=True)
    mulk_id = db.Column(db.Integer, db.ForeignKey('mulkler.id'), nullable=False)
    kiraci_id = db.Column(db.Integer, db.ForeignKey('kiracilar.id'), nullable=False)
    kira_bedeli = db.Column(db.Numeric(10, 2), nullable=False)
    baslangic_tarihi = db.Column(db.Date, nullable=False)
    bitis_tarihi = db.Column(db.Date)
    aktif_mi = db.Column(db.Boolean, default=True)
    
    odemeler = db.relationship('Odemeler', backref='sozlesme', lazy=True)

class Odemeler(db.Model):
    __tablename__ = 'odemeler'
    id = db.Column(db.Integer, primary_key=True)
    sozlesme_id = db.Column(db.Integer, db.ForeignKey('sozlesmeler.id'), nullable=False)
    odeme_donemi = db.Column(db.Date, nullable=False)
    odenen_miktar = db.Column(db.Numeric(10, 2), default=0.00)
    odeme_tarihi = db.Column(db.Date)
    durum = db.Column(db.Enum('odendi', 'eksik', 'odenmedi', 'gec_odendi'), default='odenmedi')
    aciklama = db.Column(db.Text)



with app.app_context():
    db.create_all()



@app.route('/')
def ana_sayfa():
    tum_mulkler = Mulkler.query.all()
    
    return render_template('index.html', mulkler_listesi=tum_mulkler)

@app.route('/mulk/<int:id>')
def mulk_detayi(id):
    secilen_mulk = Mulkler.query.get_or_404(id)
    
    # Şimdilik sadece mülk bilgisini detay.html'e gönderiyoruz
    # İleride kiracı ve ödemeleri de buraya bağlayacağız
    return render_template('detay.html', mulk=secilen_mulk)

@app.route('/mulk/ekle', methods=['GET', 'POST'])
def mulk_ekle():
    # Eğer form gönderildiyse (POST)
    if request.method == 'POST':
        # Formdaki "name" etiketlerinden verileri çekiyoruz
        gelen_ad = request.form.get('ad')
        gelen_tur = request.form.get('tur')
        gelen_adres = request.form.get('adres')
        
        # Yeni Mülk nesnesi oluşturup veritabanına kaydediyoruz
        yeni_mulk = Mulkler(ad=gelen_ad, tur=gelen_tur, adres=gelen_adres)
        db.session.add(yeni_mulk)
        db.session.commit()
        
        # Kayıt bitince ana sayfaya geri yönlendiriyoruz
        return redirect(url_for('ana_sayfa'))
    
    # Eğer sayfaya sadece giriş yapıldıysa (GET), boş formu göster
    return render_template('mulk_ekle.html')

@app.route('/mulk/<int:id>/kiraci_ekle', methods=['GET', 'POST'])
def kiraci_ekle(id):
    secilen_mulk = Mulkler.query.get_or_404(id)
    
    if request.method == 'POST':
        # Formdan gelen veriler
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        telefon = request.form.get('telefon')
        kira_bedeli = request.form.get('kira_bedeli')
        baslangic_tarihi_str = request.form.get('baslangic_tarihi')
        
        # String gelen tarihi Python Date objesine çeviriyoruz
        baslangic_tarihi = datetime.strptime(baslangic_tarihi_str, '%Y-%m-%d').date()
        
        # 1. Önce Kiracıyı veritabanına ekle
        yeni_kiraci = Kiracilar(ad=ad, soyad=soyad, telefon=telefon)
        db.session.add(yeni_kiraci)
        db.session.flush() # Commit yapmadan yeni kiracının ID'sini almak için flush kullanırız
        
        # 2. Şimdi Mülk ve Kiracı ID'sini birleştirip Sözleşmeyi oluştur
        yeni_sozlesme = Sozlesmeler(
            mulk_id=secilen_mulk.id,
            kiraci_id=yeni_kiraci.id,
            kira_bedeli=float(kira_bedeli),
            baslangic_tarihi=baslangic_tarihi
        )
        db.session.add(yeni_sozlesme)
        db.session.commit() # Her ikisini de kalıcı olarak kaydet
        
        return redirect(url_for('mulk_detayi', id=secilen_mulk.id))
        
    return render_template('kiraci_ekle.html', mulk=secilen_mulk)

if __name__ == '__main__':
    app.run(debug=True)