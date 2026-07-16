import os
import calendar
from datetime import datetime, date
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
    
    # (Bu Ayın Özeti) 
    bugun = date.today()
    beklenen_toplam = 0
    tahsil_edilen = 0
    
    # Sadece aktif sözleşmeleri bul
    aktif_sozlesmeler = Sozlesmeler.query.filter_by(aktif_mi=True).all()
    
    for sozlesme in aktif_sozlesmeler:
        # Bu sözleşmenin bu ayki ödemesini buluyoruz
        for odeme in sozlesme.odemeler:
            if odeme.odeme_donemi.month == bugun.month and odeme.odeme_donemi.year == bugun.year:
                beklenen_toplam += float(sozlesme.kira_bedeli)
                if odeme.durum == 'odendi':
                    tahsil_edilen += float(odeme.odenen_miktar)
                break # Bu ayın ödemesini bulduğumuz için döngüden çık

    # Yüzdeyi hesapla 
    yuzde = 0
    if beklenen_toplam > 0:
        yuzde = int((tahsil_edilen / beklenen_toplam) * 100)

    # Türkçe ay ism
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
        ad = request.form.get('ad')
        soyad = request.form.get('soyad')
        telefon = request.form.get('telefon')
        kira_bedeli = request.form.get('kira_bedeli')
        baslangic_tarihi_str = request.form.get('baslangic_tarihi')
        
        baslangic_tarihi = datetime.strptime(baslangic_tarihi_str, '%Y-%m-%d').date()
        
        # 1. Kiracıyı ekle ve ID'sini al
        yeni_kiraci = Kiracilar(ad=ad, soyad=soyad, telefon=telefon)
        db.session.add(yeni_kiraci)
        db.session.flush() 
        
        # 2. Sözleşmeyi ekle ve ID'sini al
        yeni_sozlesme = Sozlesmeler(
            mulk_id=secilen_mulk.id,
            kiraci_id=yeni_kiraci.id,
            kira_bedeli=float(kira_bedeli),
            baslangic_tarihi=baslangic_tarihi
        )
        db.session.add(yeni_sozlesme)
        db.session.flush() # Sözleşme ID'sini almak için tekrar flush yapıyoruz
        
        # 3. 12 Aylık Ödeme Tablosunu Otomatik Oluşturma Döngüsü
        for i in range(12):
            # İlgili ay ve yılı hesaplıyoruz
            ay = baslangic_tarihi.month - 1 + i
            yil = baslangic_tarihi.year + ay // 12
            ay = ay % 12 + 1
            
            # Seçili ayın kaç gün çektiğini bulup (örn: Şubat 28), gün taşmasını engelliyoruz
            max_gun = calendar.monthrange(yil, ay)[1]
            gun = min(baslangic_tarihi.day, max_gun)
            
            odeme_donemi_tarihi = date(yil, ay, gun)
            
            yeni_odeme = Odemeler(
                sozlesme_id=yeni_sozlesme.id,
                odeme_donemi=odeme_donemi_tarihi,
                durum='odenmedi' # Varsayılan olarak ödenmedi atıyoruz
            )
            db.session.add(yeni_odeme)
            
        # Tüm işlemleri (Kiracı, Sözleşme, 12 Ay Ödeme) tek seferde veritabanına kaydet
        db.session.commit()
        
        return redirect(url_for('mulk_detayi', id=secilen_mulk.id))
        
    return render_template('kiraci_ekle.html', mulk=secilen_mulk)

@app.route('/odeme/<int:id>/ode', methods=['POST'])
def odeme_yap(id):
    # İlgili ödemeyi veritabanından bul
    odeme = Odemeler.query.get_or_404(id)
    
    # Durumunu 'odendi' yap
    odeme.durum = 'odendi'
    
    # Ödenen miktarı sözleşmedeki beklenen kira bedeline eşitle
    odeme.odenen_miktar = odeme.sozlesme.kira_bedeli
    
    # Ödeme tarihini bugünün tarihi olarak ata
    odeme.odeme_tarihi = date.today()
    
    # Değişiklikleri veritabanına kaydet
    db.session.commit()
    
    # İşlem bitince kullanıcının geldiği mülk detay sayfasına geri döndür
    return redirect(url_for('mulk_detayi', id=odeme.sozlesme.mulk_id))

@app.route('/mulk/<int:id>/sil', methods=['POST'])
def mulk_sil(id):
    mulk = Mulkler.query.get_or_404(id)
    
    # SQL Hatası (Integrity Error) almamak için önce ilişkili alt verileri temizliyoruz
    for sozlesme in mulk.sozlesmeler:
        for odeme in sozlesme.odemeler:
            db.session.delete(odeme) # Önce ödemeler silinir
        db.session.delete(sozlesme)  # Sonra sözleşmeler silinir
        
    db.session.delete(mulk) # En son ana mülk silinir
    db.session.commit()
    
    return redirect(url_for('ana_sayfa'))

@app.route('/sozlesme/<int:id>/bitir', methods=['POST'])
def sozlesme_bitir(id):
    sozlesme = Sozlesmeler.query.get_or_404(id)
    
    # Geçmişi silmiyoruz, sadece sözleşmeyi pasife çekiyoruz
    sozlesme.aktif_mi = False
    
    # İsteğe bağlı: Henüz tarihi gelmemiş ve ödenmemiş gelecek ay kartlarını temizleyebilirsin
    # Sadece ödenmiş ve eksik ödenmiş kartlar geçmiş olarak veritabanında kalır
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
        # Formdan gelen yeni verilerle mevcut nesneleri güncelliyoruz
        kiraci.ad = request.form.get('ad')
        kiraci.soyad = request.form.get('soyad')
        kiraci.telefon = request.form.get('telefon')
        sozlesme.kira_bedeli = float(request.form.get('kira_bedeli'))
        
        # Tarih güncellemesini ödeme tablosunu bozmaması için şimdilik dışarıda bırakıyoruz,
        # Sadece isim, soyisim, telefon ve kira bedeli güncelleniyor.
        
        db.session.commit()
        return redirect(url_for('mulk_detayi', id=sozlesme.mulk_id))
        
    return render_template('kiraci_duzenle.html', sozlesme=sozlesme, kiraci=kiraci)

if __name__ == '__main__':
    app.run(debug=True)