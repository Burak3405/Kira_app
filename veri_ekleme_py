from main import app, db, Mulkler, Kiracilar


with app.app_context():
    
   
    yeni_mulk = Mulkler(ad="Moda 2+1 Daire", tur="Ev", adres="Moda Cad. No:123 Kadıköy")
    
  
    yeni_kiraci = Kiracilar(ad="Ahmet", soyad="Yılmaz", telefon="05551234567")
    
    
    db.session.add(yeni_mulk)
    db.session.add(yeni_kiraci)
    
   
    db.session.commit()
    
    tum_kiracilar = Kiracilar.query.all()
    print(tum_kiracilar)
    
    print("Tebrikler! İlk mülk ve kiracı veritabanına başarıyla eklendi.")