import os
import calendar
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

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
    
    #İSTATİSTİK HESAPLAMA(Ayın Özeti) ---
    bugun = date.today()
    beklenen_toplam = 0
    tahsil_edilen = 0
    
    # Aktif sözleşmeleri bul
    aktif_sozlesmeler = Sozlesmeler.query.filter_by(aktif_mi=True).all()
    
    for sozlesme in aktif_sozlesmeler:
        # Bu ayki ödemesini buluyoruz
        for odeme in sozlesme.odemeler:
            if odeme.odeme_donemi.month == bugun.month and odeme.odeme_donemi.year == bugun.year:
                beklenen_toplam += float(sozlesme.kira_bedeli)
                
                if odeme.durum == 'odendi' or odeme.durum == 'eksik':
                    tahsil_edilen += float(odeme.odenen_miktar)
                
                break 

    # Yüzde
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
def mulk_detayi(id):
    secilen_mulk = Mulkler.query.get_or_404(id)
    
    return render_template('detay.html', mulk=secilen_mulk)

@app.route('/mulk/ekle', methods=['GET', 'POST'])
def mulk_ekle():
    
    if request.method == 'POST':
        # "name" den verileri çekiyoruz
        gelen_ad = request.form.get('ad')
        gelen_tur = request.form.get('tur')
        gelen_adres = request.form.get('adres')
        
        
        yeni_mulk = Mulkler(ad=gelen_ad, tur=gelen_tur, adres=gelen_adres)
        db.session.add(yeni_mulk)
        db.session.commit()
        
        # Kayıt bitince ana sayfaya geri yönlendiriyoruz
        return redirect(url_for('ana_sayfa'))
    
    
    return render_template('mulk_ekle.html')

@app.route('/mulk/<int:id>/kiraci_ekle', methods=['GET', 'POST'])
def kiraci_ekle(id):
    secilen_mulk = Mulkler.query.get_or_404(id)
    
    if request.method == 'POST':
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        telefon = request.form.get('telefon')
        kira_bedeli = request.form.get('kira_bedeli')
        baslangic_tarihi_str = request.form.get('baslangic_tarihi')
        
        baslangic_tarihi = datetime.strptime(baslangic_tarihi_str, '%Y-%m-%d').date()
        
        # 1. Kiracıyı ekle ve ID sini al
        yeni_kiraci = Kiracilar(ad=ad, soyad=soyad, telefon=telefon)
        db.session.add(yeni_kiraci)
        db.session.flush() 
        
        # 2. Sözleşmeyi ekle ve ID sini al
        yeni_sozlesme = Sozlesmeler(
            mulk_id=secilen_mulk.id,
            kiraci_id=yeni_kiraci.id,
            kira_bedeli=float(kira_bedeli),
            baslangic_tarihi=baslangic_tarihi
        )
        db.session.add(yeni_sozlesme)
        db.session.flush() # Sözleşme ID sini almak için tekrar flush yapılır
        
        # 3. 12 Ödeme tablosunu otomatik oluşturma döngüsü
        for i in range(12):
            ay = baslangic_tarihi.month - 1 + i
            yil = baslangic_tarihi.year + ay // 12
            ay = ay % 12 + 1
            
            # Ayın kaç gün çektiğini bulma
            max_gun = calendar.monthrange(yil, ay)[1]
            gun = min(baslangic_tarihi.day, max_gun)
            
            odeme_donemi_tarihi = date(yil, ay, gun)
            
            yeni_odeme = Odemeler(
                sozlesme_id=yeni_sozlesme.id,
                odeme_donemi=odeme_donemi_tarihi,
                durum='odenmedi' # Varsayılan = ödemedi
            )
            db.session.add(yeni_odeme)
            
        # Tüm işlemleri tek seferde veritabanına kaydet
        db.session.commit()
        
        return redirect(url_for('mulk_detayi', id=secilen_mulk.id))
        
    return render_template('kiraci_ekle.html', mulk=secilen_mulk)

@app.route('/odeme/<int:id>/ode', methods=['POST'])
def odeme_yap(id):
    # İlgili ödemeyi veritabanından bul
    odeme = Odemeler.query.get_or_404(id)
    
    odeme.durum = 'odendi'
    
    odeme.odenen_miktar = odeme.sozlesme.kira_bedeli
    
    odeme.odeme_tarihi = date.today()
    
    db.session.commit()
    
    # İşlem bitince kullanıcının geldiği mülk detay sayfasına geri döndür
    return redirect(url_for('mulk_detayi', id=odeme.sozlesme.mulk_id))

@app.route('/mulk/<int:id>/sil', methods=['POST'])
def mulk_sil(id):
    mulk = Mulkler.query.get_or_404(id)
    
    # Integrity Error almamak için 
    for sozlesme in mulk.sozlesmeler:
        for odeme in sozlesme.odemeler:
            db.session.delete(odeme) 
        db.session.delete(sozlesme)  
        
    db.session.delete(mulk) 
    db.session.commit()
    
    return redirect(url_for('ana_sayfa'))

@app.route('/sozlesme/<int:id>/bitir', methods=['POST'])
def sozlesme_bitir(id):
    sozlesme = Sozlesmeler.query.get_or_404(id)
    
    
    sozlesme.aktif_mi = False
    
    
    for odeme in sozlesme.odemeler:
        if odeme.durum == 'odenmedi':
            db.session.delete(odeme)
            
    db.session.commit()
    return redirect(url_for('mulk_detayi', id=sozlesme.mulk_id))

@app.route('/sozlesme/<int:id>/duzenle', methods=['GET', 'POST'])
def kiraci_duzenle(id):
    sozlesme = Sozlesmeler.query.get_or_404(id)
    kiraci = sozlesme.kiraci
    
    if request.method == 'POST':
        
        kiraci.ad = request.form.get('ad')
        kiraci.soyad = request.form.get('soyad')
        kiraci.telefon = request.form.get('telefon')
        sozlesme.kira_bedeli = float(request.form.get('kira_bedeli'))
        
        db.session.commit()
        return redirect(url_for('mulk_detayi', id=sozlesme.mulk_id))
        
    return render_template('kiraci_duzenle.html', sozlesme=sozlesme, kiraci=kiraci)

@app.route('/odeme/<int:id>/detayli_ode', methods=['POST'])
def detayli_odeme_yap(id):
    odeme = Odemeler.query.get_or_404(id)

    # Formdan gelen verileri alıyoruz
    gelen_miktar = request.form.get('odenen_miktar')
    gelen_tarih = request.form.get('odeme_tarihi')
    aciklama = request.form.get('aciklama')
    
    # 1. Ödenen Miktarı ata 
    odeme.odenen_miktar = float(gelen_miktar)
    
    # 2. Tarih girilmemişse bugünü ata
    if gelen_tarih:
        odeme.odeme_tarihi = datetime.strptime(gelen_tarih, '%Y-%m-%d').date()
    else:
        odeme.odeme_tarihi = date.today()
        
    odeme.aciklama = aciklama
    
    # 3. Durumu güncelle 
    if odeme.odenen_miktar >= odeme.sozlesme.kira_bedeli:
        odeme.durum = 'odendi'
    else:
        odeme.durum = 'eksik'
        
    db.session.commit()
    return redirect(url_for('mulk_detayi', id=odeme.sozlesme.mulk_id))


if __name__ == '__main__':
    app.run(debug=True)