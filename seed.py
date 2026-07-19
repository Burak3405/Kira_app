from main import app, db, Mulkler, Kiracilar, Kullanicilar

with app.app_context():
    
    # 1. Sisteme test için bir kullanıcı ekle(Eğer yoksa)
    test_kullanici = Kullanicilar.query.filter_by(kullanici_adi="test_admin").first()
    
    if not test_kullanici:
        test_kullanici = Kullanicilar(kullanici_adi="test_admin")
        test_kullanici.sifre_belirle("123456") 
        db.session.add(test_kullanici)
        db.session.commit() 
        print("Test kullanıcısı oluşturuldu.")

    # 2. Mülkü oluştur 
    yeni_mulk = Mulkler(
        ad="Moda 2+1 Daire", 
        tur="Ev", 
        adres="Moda Cad. No:123 Kadıköy",
        kullanici_id=test_kullanici.id
    )
    
    
    yeni_kiraci = Kiracilar(
        ad="Ahmet", 
        soyad="Yılmaz", 
        telefon="0**********",
        kullanici_id=test_kullanici.id
    )
    
    db.session.add(yeni_mulk)
    db.session.add(yeni_kiraci)
    
    db.session.commit()
    
    tum_kiracilar = Kiracilar.query.all()
    print(tum_kiracilar)
    
    print("Tebrikler! İlk mülk ve kiracı veritabanına başarıyla eklendi.")