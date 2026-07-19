import os
import calendar
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, DateField, SelectField, PasswordField, BooleanField
from wtforms.validators import DataRequired, Length, NumberRange, Optional, InputRequired
from werkzeug.exceptions import HTTPException

load_dotenv()

app = Flask(__name__)

# Proxy arkasında çalışırken gerçek IP'leri yakalamak için middleware 
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri="memory://" 
)

csrf = CSRFProtect(app)

@app.errorhandler(429)
def ratelimit_handler(e):
    flash("Çok fazla giriş denemesi yaptınız. Lütfen 1 dakika bekleyip tekrar deneyin.", "error")
    return redirect(url_for('login'))

app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['ADMIN_USERNAME'] = os.getenv('ADMIN_USERNAME')

app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=30)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

app.config['SESSION_COOKIE_SECURE'] = os.getenv('FLASK_ENV') == 'production'


db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login' 

@login_manager.user_loader
def load_user(kullanici_id):
    return db.session.get(Kullanicilar, int(kullanici_id))

class Kullanicilar(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    kullanici_adi = db.Column(db.String(50), unique=True, nullable=False)
    sifre_hash = db.Column(db.String(255), nullable=False)
    
    # Kullanıcının mülkleri ve kiracıları ile ilişkisi
    mulkler = db.relationship('Mulkler', backref='sahip', lazy=True)
    kiracilar = db.relationship('Kiracilar', backref='sahip', lazy=True)

    def sifre_belirle(self, sifre):
        self.sifre_hash = generate_password_hash(sifre)

    def sifre_kontrol(self, sifre):
        return check_password_hash(self.sifre_hash, sifre)

class Mulkler(db.Model):
    __tablename__ = 'mulkler'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(100), nullable=False)
    tur = db.Column(db.String(50), nullable=False)
    adres = db.Column(db.Text)
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.now)
    
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanicilar.id'), nullable=False)
    sozlesmeler = db.relationship('Sozlesmeler', backref='mulk', lazy=True)

class Kiracilar(db.Model):
    __tablename__ = 'kiracilar'
    id = db.Column(db.Integer, primary_key=True)
    ad = db.Column(db.String(50), nullable=False)
    soyad = db.Column(db.String(50), nullable=False)
    telefon = db.Column(db.String(20))
    olusturulma_tarihi = db.Column(db.DateTime, default=datetime.now)
    
    kullanici_id = db.Column(db.Integer, db.ForeignKey('kullanicilar.id'), nullable=False)

    sozlesmeler = db.relationship('Sozlesmeler', backref='kiraci', lazy=True)

class Sozlesmeler(db.Model):
    __tablename__ = 'sozlesmeler'
    id = db.Column(db.Integer, primary_key=True)
    mulk_id = db.Column(db.Integer, db.ForeignKey('mulkler.id'), nullable=False)
    kiraci_id = db.Column(db.Integer, db.ForeignKey('kiracilar.id'), nullable=False)
    kira_bedeli = db.Column(db.Numeric(10, 2), nullable=False)
    kapora = db.Column(db.String(100), nullable=True) 
    aktif_mi = db.Column(db.Boolean, default=True) #?
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


class KayitForm(FlaskForm):
    kullanici_adi = StringField('Kullanıcı Adı', validators=[
        DataRequired(message="Kullanıcı adı boş bırakılamaz."),
        Length(min=3, max=50, message="Kullanıcı adı 3 ile 50 karakter arasında olmalıdır.")
    ])
    sifre = PasswordField('Şifre', validators=[
        DataRequired(message="Şifre boş bırakılamaz."),
        Length(min=6, max=100, message="Şifre en az 6 karakter olmalıdır.")
    ])

class GirisForm(FlaskForm):
    kullanici_adi = StringField('Kullanıcı Adı', validators=[DataRequired(message="Kullanıcı adınızı giriniz.")])
    sifre = PasswordField('Şifre', validators=[DataRequired(message="Şifrenizi giriniz.")])
    beni_hatirla = BooleanField('Beni Hatırla')

class KiraciEkleForm(FlaskForm):
    
    ad = StringField('Ad', validators=[
        DataRequired(message="Ad alanı zorunludur."), 
        Length(min=2, max=50, message="Ad 2 ile 50 karakter arasında olmalıdır.")
    ])
    soyad = StringField('Soyad', validators=[
        DataRequired(message="Soyad alanı zorunludur."), 
        Length(min=2, max=50, message="Soyad 2 ile 50 karakter arasında olmalıdır.")
    ])
    telefon = StringField('Telefon', validators=[
        Optional(), 
        Length(max=20, message="Telefon numarası çok uzun.")
    ])
    kira_bedeli = FloatField('Kira Bedeli', validators=[
        DataRequired(message="Geçerli bir kira bedeli giriniz."), 
        NumberRange(min=0, max=99999999, message="Kira bedeli sistem sınırlarını aşıyor (Min: 0, Maks: 99.999.999).")
    ])
    kapora = StringField('Kapora', validators=[
        Optional(), 
        Length(max=100)
    ])
    baslangic_tarihi = DateField('Başlangıç Tarihi', format='%Y-%m-%d', validators=[
        DataRequired(message="Geçerli bir tarih formatı giriniz.")
    ])

class MulkEkleForm(FlaskForm):
    ad = StringField('Ad', validators=[
        DataRequired(message="Mülk adı zorunludur."), 
        Length(max=100, message="Mülk adı çok uzun.")
    ])
    tur = SelectField('Tür', choices=[
        ('Ev (Daire)', 'Ev (Daire)'), 
        ('Dükkan / İş Yeri', 'Dükkan / İş Yeri'), 
        ('Ofis', 'Ofis'), 
        ('Müstakil Ev', 'Müstakil Ev'), 
        ('Arsa', 'Arsa'), 
        ('Diğer', 'Diğer')
    ], validators=[DataRequired(message="Geçerli bir mülk türü seçiniz.")])
    adres = StringField('Adres', validators=[Optional()])

class SozlesmeYenileForm(FlaskForm):
    kira_bedeli = FloatField('Yeni Kira Bedeli', validators=[
        InputRequired(message="Geçerli bir kira bedeli giriniz."), 
        NumberRange(min=0, message="Kira bedeli eksi olamaz.")
    ])
    baslangic_tarihi = DateField('Başlangıç Tarihi', format='%Y-%m-%d', validators=[
        DataRequired(message="Geçerli bir başlangıç tarihi giriniz.")
    ])

class OdemeForm(FlaskForm):
    # Sıfır girilebilmesi 
    odenen_miktar = FloatField('Ödenen Miktar', validators=[
        InputRequired(message="Geçerli bir miktar giriniz."), 
        NumberRange(min=0, max=99999999, message="Ödeme miktarı sistem sınırlarını aşıyor (Min: 0, Maks: 99.999.999).")
    ])
    odeme_tarihi = DateField('Ödeme Tarihi', format='%Y-%m-%d', validators=[Optional()])
    aciklama = StringField('Açıklama', validators=[Optional(), Length(max=255)])

class KiraciDuzenleForm(FlaskForm):
    ad = StringField('Ad', validators=[
        DataRequired(message="Ad alanı zorunludur."),
        Length(min=2, max=50, message="Ad 2 ile 50 karakter arasında olmalıdır.")
    ])
    soyad = StringField('Soyad', validators=[
        DataRequired(message="Soyad alanı zorunludur."),
        Length(min=2, max=50, message="Soyad 2 ile 50 karakter arasında olmalıdır.")
    ])
    telefon = StringField('Telefon', validators=[
        Optional(),
        Length(max=20, message="Telefon numarası çok uzun.")
    ])
    kira_bedeli = FloatField('Kira Bedeli', validators=[
        InputRequired(message="Geçerli bir kira bedeli giriniz."),
        NumberRange(min=0, max=99999999, message="Kira bedeli sistem sınırlarını aşıyor (Maks: 99.999.999).")
    ])
    kapora = StringField('Kapora', validators=[
        Optional(),
        Length(max=100, message="Kapora metni çok uzun.")
    ])


with app.app_context():
    db.create_all()

# --- AUTH ROTALARI (GİRİŞ / ÇIKIŞ / KAYIT) ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = KayitForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            kullanici_adi = form.kullanici_adi.data.strip()
            sifre = form.sifre.data
            
            mevcut_kullanici = Kullanicilar.query.filter_by(kullanici_adi=kullanici_adi).first()
            if mevcut_kullanici:
                flash('Bu kullanıcı adı zaten alınmış. Lütfen başka bir tane seçin.', 'error')
                return redirect(url_for('register'))
                
            yeni_kullanici = Kullanicilar(kullanici_adi=kullanici_adi)
            yeni_kullanici.sifre_belirle(sifre)
            
            db.session.add(yeni_kullanici)
            db.session.commit()
            
            flash('Kayıt başarılı! Şimdi giriş yapabilirsiniz.', 'success')
            return redirect(url_for('login'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
            
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("3 per minute", methods=["POST"])
def login():
    form = GirisForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            kullanici_adi = form.kullanici_adi.data.strip()
            sifre = form.sifre.data
            beni_hatirla = form.beni_hatirla.data
            
            kullanici = Kullanicilar.query.filter_by(kullanici_adi=kullanici_adi).first()
            
            if kullanici and kullanici.sifre_kontrol(sifre):
                login_user(kullanici, remember=beni_hatirla)
                
                admin_kullanici = app.config.get('ADMIN_USERNAME')
                if admin_kullanici and kullanici.kullanici_adi == admin_kullanici.strip(): 
                    return redirect(url_for('admin_panel'))
                
                return redirect(url_for('ana_sayfa'))
            else:
                flash('Hatalı kullanıcı adı veya şifre!', 'error')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
            
    return render_template('login.html')

@app.route('/cerez-politikasi')
def cerez_politikasi():
    return render_template('cerez_politikasi.html')

@app.route('/gizlilik')
def gizlilik_politikasi():
    return render_template('gizlilik.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def ana_sayfa():
    tum_mulkler = Mulkler.query.filter_by(kullanici_id=current_user.id).all()
    
    #Ayın Özeti
    bugun = date.today()
    beklenen_toplam = 0
    tahsil_edilen = 0
    
   
    aktif_sozlesmeler = Sozlesmeler.query.join(Mulkler).filter(
        Sozlesmeler.aktif_mi == True, 
        Mulkler.kullanici_id == current_user.id
    ).all()
    
    for sozlesme in aktif_sozlesmeler:
        
        for odeme in sozlesme.odemeler:
            if odeme.odeme_donemi.month == bugun.month and odeme.odeme_donemi.year == bugun.year:
                beklenen_toplam += float(sozlesme.kira_bedeli)
                
                if odeme.durum == 'odendi' or odeme.durum == 'eksik':
                    tahsil_edilen += float(odeme.odenen_miktar)
                
                break 

    
    yuzde = 0
    if beklenen_toplam > 0:
        yuzde = int((tahsil_edilen / beklenen_toplam) * 100)

    # Türkçe ay isimleri
    aylar = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']
    
    # Türkçe para formatı
    def tr_format(deger):
        return f"{deger:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

    istatistik = {
        'beklenen': tr_format(beklenen_toplam),
        'tahsil_edilen': tr_format(tahsil_edilen),
        'yuzde': yuzde,
        'ay_ismi': aylar[bugun.month - 1],
        'yil': bugun.year
    }
    
    return render_template('index.html', mulkler_listesi=tum_mulkler, istatistik=istatistik)

@app.route('/mulk/<int:id>')
@login_required
def mulk_detayi(id):
    secilen_mulk = Mulkler.query.filter_by(id=id, kullanici_id=current_user.id).first_or_404()
    
    sozlesme_bitti_mi = False
    bitis_tarihi = None
    
    # 1. Mülkün içindeki AKTİF sözleşmeyi bul
    aktif_sozlesme = next((s for s in secilen_mulk.sozlesmeler if s.aktif_mi), None)
    
    # 2. Mülkün içindeki GEÇMİŞ (pasif) sözleşmeleri bul ve en yeniden eskiye doğru sırala
    gecmis_sozlesmeler = [s for s in secilen_mulk.sozlesmeler if not s.aktif_mi]
    gecmis_sozlesmeler.sort(key=lambda x: x.baslangic_tarihi, reverse=True)
    
    if aktif_sozlesme:
        try:
            bitis_tarihi = aktif_sozlesme.baslangic_tarihi.replace(year=aktif_sozlesme.baslangic_tarihi.year + 1)
        except ValueError:
            bitis_tarihi = aktif_sozlesme.baslangic_tarihi.replace(year=aktif_sozlesme.baslangic_tarihi.year + 1, day=28)
        
        if date.today() >= bitis_tarihi:
            sozlesme_bitti_mi = True

    aylar = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

    return render_template('detay.html', 
                           mulk=secilen_mulk, 
                           aktif_sozlesme=aktif_sozlesme,
                           gecmis_sozlesmeler=gecmis_sozlesmeler, 
                           sozlesme_bitti_mi=sozlesme_bitti_mi, 
                           bitis_tarihi=bitis_tarihi,
                           aylar=aylar)

@app.route('/sozlesme/<int:id>/yenile', methods=['GET', 'POST'])
@login_required
def sozlesme_yenile(id):
    eski_sozlesme = Sozlesmeler.query.get_or_404(id)
    mulk = eski_sozlesme.mulk
    if mulk.kullanici_id != current_user.id:
        return redirect(url_for('ana_sayfa'))
    
    kiraci = eski_sozlesme.kiraci
    form = SozlesmeYenileForm()
    
    try:
        varsayilan_baslangic = eski_sozlesme.baslangic_tarihi.replace(year=eski_sozlesme.baslangic_tarihi.year + 1)
    except ValueError:
        varsayilan_baslangic = eski_sozlesme.baslangic_tarihi.replace(year=eski_sozlesme.baslangic_tarihi.year + 1, day=28)
        
    if request.method == 'POST':
        if form.validate_on_submit():
            eski_sozlesme.aktif_mi = False
            
            yeni_sozlesme = Sozlesmeler(
                mulk_id=mulk.id,
                kiraci_id=kiraci.id,
                kira_bedeli=form.kira_bedeli.data,
                baslangic_tarihi=form.baslangic_tarihi.data
            )
            db.session.add(yeni_sozlesme)
            db.session.flush() 
            
            yeni_baslangic = form.baslangic_tarihi.data
            for i in range(12):
                ay = yeni_baslangic.month - 1 + i
                yil = yeni_baslangic.year + ay // 12
                ay = ay % 12 + 1
                max_gun = calendar.monthrange(yil, ay)[1]
                gun = min(yeni_baslangic.day, max_gun)
                
                odeme_donemi_tarihi = date(yil, ay, gun)
                yeni_odeme = Odemeler(
                    sozlesme_id=yeni_sozlesme.id,
                    odeme_donemi=odeme_donemi_tarihi,
                    durum='odenmedi'
                )
                db.session.add(yeni_odeme)
                
            db.session.commit()
            flash('Sözleşme başarıyla yenilendi.', 'success')
            return redirect(url_for('mulk_detayi', id=mulk.id))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
                    
    return render_template('sozlesme_yenile.html', eski_sozlesme=eski_sozlesme, kiraci=kiraci, varsayilan_baslangic=varsayilan_baslangic)

@app.route('/mulk/ekle', methods=['GET', 'POST'])
@login_required
def mulk_ekle():
    form = MulkEkleForm()
    
    if request.method == 'POST':
        if form.validate_on_submit():
            yeni_mulk = Mulkler(
                ad=form.ad.data.strip(), 
                tur=form.tur.data, 
                adres=form.adres.data.strip() if form.adres.data else None, 
                kullanici_id=current_user.id
            )
            db.session.add(yeni_mulk)
            db.session.commit()
            
            flash('Yeni mülk başarıyla eklendi.', 'success')
            return redirect(url_for('ana_sayfa'))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
                    
    return render_template('mulk_ekle.html')

@app.route('/mulk/<int:id>/kiraci_ekle', methods=['GET', 'POST'])
@login_required
def kiraci_ekle(id):
    secilen_mulk = Mulkler.query.filter_by(id=id, kullanici_id=current_user.id).first_or_404()
    
    
    form = KiraciEkleForm() 
    
    if request.method == 'POST':
        if form.validate_on_submit():
            # Veriler form.xyz.data diyerek güvenli ve doğru tipte (Float, Date vb.) alınır
            yeni_kiraci = Kiracilar(
                ad=form.ad.data.strip(), 
                soyad=form.soyad.data.strip(), 
                telefon=form.telefon.data.strip() if form.telefon.data else None, 
                kullanici_id=current_user.id
            )
            db.session.add(yeni_kiraci)
            db.session.flush() 
            
            yeni_sozlesme = Sozlesmeler(
                mulk_id=secilen_mulk.id,
                kiraci_id=yeni_kiraci.id,
                kira_bedeli=form.kira_bedeli.data, # Doğrudan float olarak gelir
                baslangic_tarihi=form.baslangic_tarihi.data, # Doğrudan Date objesi olarak gelir
                kapora=form.kapora.data.strip() if form.kapora.data else None
            )
            db.session.add(yeni_sozlesme)
            db.session.flush() 
            
            baslangic_tarihi = form.baslangic_tarihi.data
            for i in range(12):
                ay = baslangic_tarihi.month - 1 + i
                yil = baslangic_tarihi.year + ay // 12
                ay = ay % 12 + 1
                max_gun = calendar.monthrange(yil, ay)[1]
                gun = min(baslangic_tarihi.day, max_gun)
                
                odeme_donemi_tarihi = date(yil, ay, gun)
                yeni_odeme = Odemeler(
                    sozlesme_id=yeni_sozlesme.id,
                    odeme_donemi=odeme_donemi_tarihi,
                    durum='odenmedi' 
                )
                db.session.add(yeni_odeme)
                
            db.session.commit()
            flash('Kiracı ve sözleşme başarıyla eklendi.', 'success')
            return redirect(url_for('mulk_detayi', id=secilen_mulk.id))
            
        else:
            for field_name, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
                    
    return render_template('kiraci_ekle.html', mulk=secilen_mulk)

@app.route('/odeme/<int:id>/ode', methods=['POST'])
@login_required
def odeme_yap(id):
    # İlgili ödemeyi bul
    odeme = Odemeler.query.get_or_404(id)
    if odeme.sozlesme.mulk.kullanici_id != current_user.id:
        return redirect(url_for('ana_sayfa'))
    
    odeme.durum = 'odendi'
    
    odeme.odenen_miktar = odeme.sozlesme.kira_bedeli
    
    odeme.odeme_tarihi = date.today()
    
    db.session.commit()
    
    
    return redirect(url_for('mulk_detayi', id=odeme.sozlesme.mulk_id))

@app.route('/mulk/<int:id>/sil', methods=['POST'])
@login_required
def mulk_sil(id):
    mulk = Mulkler.query.filter_by(id=id, kullanici_id=current_user.id).first_or_404()
    
    silinecek_kiracilar = set()
    
    for sozlesme in mulk.sozlesmeler:
        if sozlesme.kiraci:
            silinecek_kiracilar.add(sozlesme.kiraci)
            
        for odeme in sozlesme.odemeler:
            db.session.delete(odeme) 
        db.session.delete(sozlesme)  
        
    db.session.delete(mulk) 
    
    for kiraci in silinecek_kiracilar:
        db.session.delete(kiraci)
        
    db.session.commit()
    
    return redirect(url_for('ana_sayfa'))

@app.route('/sozlesme/<int:id>/bitir', methods=['POST'])
@login_required
def sozlesme_bitir(id):
    sozlesme = Sozlesmeler.query.get_or_404(id)
    if sozlesme.mulk.kullanici_id != current_user.id:
        return redirect(url_for('ana_sayfa'))
    
    
    sozlesme.aktif_mi = False
    
    
    for odeme in sozlesme.odemeler:
        if odeme.durum == 'odenmedi':
            db.session.delete(odeme)
            
    db.session.commit()
    return redirect(url_for('mulk_detayi', id=sozlesme.mulk_id))


@app.route('/sozlesme/<int:id>/duzenle', methods=['GET', 'POST'])
@login_required
def kiraci_duzenle(id):
    sozlesme = Sozlesmeler.query.get_or_404(id)
    if sozlesme.mulk.kullanici_id != current_user.id:
        return redirect(url_for('ana_sayfa'))
    
    kiraci = sozlesme.kiraci
    form = KiraciDuzenleForm()
    
    
    if request.method == 'GET':
        form.ad.data = kiraci.ad
        form.soyad.data = kiraci.soyad
        form.telefon.data = kiraci.telefon
        form.kira_bedeli.data = sozlesme.kira_bedeli
        form.kapora.data = sozlesme.kapora
        
    if request.method == 'POST':
        if form.validate_on_submit():
            kiraci.ad = form.ad.data.strip()
            kiraci.soyad = form.soyad.data.strip()
            kiraci.telefon = form.telefon.data.strip() if form.telefon.data else None
            sozlesme.kira_bedeli = form.kira_bedeli.data
            sozlesme.kapora = form.kapora.data.strip() if form.kapora.data else None
            
            db.session.commit()
            flash('Bilgiler başarıyla güncellendi.', 'success')
            return redirect(url_for('mulk_detayi', id=sozlesme.mulk_id))
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    flash(error, 'error')
                    
    
    return render_template('kiraci_duzenle.html', sozlesme=sozlesme, kiraci=kiraci, form=form)

@app.route('/odeme/<int:id>/detayli_ode', methods=['POST'])
@login_required
def detayli_odeme_yap(id):
    odeme = Odemeler.query.get_or_404(id)
    if odeme.sozlesme.mulk.kullanici_id != current_user.id:
        return redirect(url_for('ana_sayfa'))

    form = OdemeForm()
    if form.validate_on_submit():
        odeme.odenen_miktar = form.odenen_miktar.data
        odeme.odeme_tarihi = form.odeme_tarihi.data if form.odeme_tarihi.data else date.today()
        odeme.aciklama = form.aciklama.data.strip() if form.aciklama.data else None
        
        if odeme.odenen_miktar >= odeme.sozlesme.kira_bedeli:
            odeme.durum = 'odendi'
        else:
            odeme.durum = 'eksik'
            
        db.session.commit()
        flash('Ödeme detayları kaydedildi.', 'success')
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'error')
                
    return redirect(url_for('mulk_detayi', id=odeme.sozlesme.mulk_id))

@app.route('/odeme/<int:id>/guncelle', methods=['POST'])
@login_required
def odeme_guncelle(id):
    odeme = Odemeler.query.get_or_404(id)
    if odeme.sozlesme.mulk.kullanici_id != current_user.id:
        return redirect(url_for('ana_sayfa'))
    
    form = OdemeForm()
    if form.validate_on_submit():
        gelen_miktar = form.odenen_miktar.data
        
        if gelen_miktar == 0:
            odeme.odenen_miktar = 0
            odeme.odeme_tarihi = None
            odeme.aciklama = None
            odeme.durum = 'odenmedi'
            flash('Ödeme sıfırlanıp iptal edildi.', 'success')
        else:
            odeme.odenen_miktar = gelen_miktar
            if form.odeme_tarihi.data:
                odeme.odeme_tarihi = form.odeme_tarihi.data
            odeme.aciklama = form.aciklama.data.strip() if form.aciklama.data else None
            
            if odeme.odenen_miktar >= odeme.sozlesme.kira_bedeli:
                odeme.durum = 'odendi'
            else:
                odeme.durum = 'eksik'
            flash('Ödeme başarıyla güncellendi.', 'success')
            
        db.session.commit()
    else:
        for field, errors in form.errors.items():
            for error in errors:
                flash(error, 'error')
                
    return redirect(url_for('mulk_detayi', id=odeme.sozlesme.mulk_id))


@app.route('/admin_panel')
@login_required
def admin_panel():
    admin_kullanici = app.config.get('ADMIN_USERNAME')

    if current_user.kullanici_adi != admin_kullanici:
        return redirect(url_for('ana_sayfa'))

    # Admin hariç tüm kullanıcıları listele
    kullanicilar = Kullanicilar.query.filter(Kullanicilar.kullanici_adi != admin_kullanici).all()
    
    # İstatistikler
    toplam_kullanici = len(kullanicilar)
    toplam_mulk = Mulkler.query.count()
    toplam_kiraci = Kiracilar.query.count()
    
    try:
        
        sorgu = db.text("SELECT ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) FROM information_schema.TABLES WHERE table_schema = DATABASE()")
        result = db.session.execute(sorgu)
        db_boyutu = result.scalar() or 0.0
    except Exception as e:
        db_boyutu = 0.0

    istatistikler = {
        'toplam_kullanici': toplam_kullanici,
        'toplam_mulk': toplam_mulk,
        'toplam_kiraci': toplam_kiraci,
        'db_boyutu': db_boyutu
    }

    return render_template('admin_panel.html', kullanicilar=kullanicilar, istatistikler=istatistikler)

@app.route('/admin/kullanici_sil/<int:id>', methods=['POST'])
@login_required
def kullanici_sil(id):
    admin_kullanici = app.config.get('ADMIN_USERNAME')
    if current_user.kullanici_adi != admin_kullanici:
        return redirect(url_for('ana_sayfa'))
        
    silinecek_kullanici = Kullanicilar.query.get_or_404(id)
    
    # Kullanıcıya bağlı her şeyi temizle
    for mulk in silinecek_kullanici.mulkler:
        for sozlesme in mulk.sozlesmeler:
            for odeme in sozlesme.odemeler:
                db.session.delete(odeme)
            db.session.delete(sozlesme)
        db.session.delete(mulk)
        
    # 2. Kiracıları sil
    for kiraci in silinecek_kullanici.kiracilar:
        db.session.delete(kiraci)
        
    # 3.kullanıcıyı sil
    kullanici_adi_yedek = silinecek_kullanici.kullanici_adi
    db.session.delete(silinecek_kullanici)
    db.session.commit()
    
    flash(f'{kullanici_adi_yedek} kullanıcısı ve tüm verileri sistemden kalıcı olarak silindi.', 'success')
    return redirect(url_for('admin_panel'))


@app.errorhandler(Exception)
def genel_hata_yakalayici(e):
    if isinstance(e, HTTPException):
        hata_mesajlari = {
            400: "Geçersiz istek. Lütfen gönderdiğiniz form verilerini kontrol edin.",
            401: "Bu sayfayı görüntülemek için giriş yapmalısınız.",
            403: "Erişim reddedildi. Bu işlemi yapmaya yetkiniz yok.",
            404: "Aradığınız sayfa bulunamamış veya silinmiş olabilir.",
            405: "Bu sayfa için kullanılan yöntem geçerli değil."
        }
        
        mesaj = hata_mesajlari.get(e.code, e.description)
        return render_template('hata.html', hata_kodu=e.code, mesaj=mesaj), e.code

    return render_template('hata.html', hata_kodu=500, mesaj="Beklenmeyen bir hata oluştu"), 500



if __name__ == '__main__':
    app.run(debug=False) 

