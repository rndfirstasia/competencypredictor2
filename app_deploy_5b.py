import streamlit as st
import pandas as pd
import boto3
from datetime import datetime
import mysql.connector
from mysql.connector import Error

from openai import OpenAI
import openai
import requests
import io
from io import StringIO
from collections import defaultdict
import pytz #datetime sesuai zona waktu indon

#page config
st.set_page_config(
    page_icon="img/icon.png",
    page_title="Prediksi Kompetensi",
)

#env
#untuk deploy
aws_access_key_id = st.secrets["aws"]["aws_access_key_id"]
aws_secret_access_key = st.secrets["aws"]["aws_secret_access_key"]
endpoint_url = st.secrets["aws"]["endpoint_url"]
mysql_user = st.secrets["mysql"]["username"]
mysql_password = st.secrets["mysql"]["password"]
mysql_host = st.secrets["mysql"]["host"]
mysql_port = st.secrets["mysql"]["port"]
mysql_database = st.secrets["mysql"]["database"]
client = OpenAI(api_key=st.secrets["openai"]["api"])
openai.api_key = st.secrets["openai"]["api"]
hf_token = st.secrets["hf"]["token"]
flask_url = st.secrets["flask"]["url"]
 #untuk API PITO
pito_url = st.secrets["sistem_fac"]["pito_url"]
vast_url = st.secrets["sistem_fac"]["vast_url"]
pito_api_user = st.secrets["sistem_fac"]["pito_api_user"]
pito_api_key = st.secrets["sistem_fac"]["pito_api_key"]
vast_api_user = st.secrets["sistem_fac"]["vast_api_user"]
vast_api_key = st.secrets["sistem_fac"]["vast_api_key"]

base_urls = {
    "PITO": pito_url,
    "VAST": vast_url
}

conn = mysql.connector.connect(
    user=mysql_user,
    password=mysql_password,
    host=mysql_host,
    port=mysql_port,
    database=mysql_database
)

connx = conn.cursor() 

def create_db_connection():
    try:
        conn = mysql.connector.connect(
            user=mysql_user,
            password=mysql_password,
            host=mysql_host,
            port=mysql_port,
            database=mysql_database
        )
        if conn.is_connected():
            return conn
        else:
            return None
    except Error as e:
        print(f"Error while connecting to MySQL: {e}")
        return None

connx.execute('SELECT * FROM txtan_assessor;')
df_txtan_assessor = connx.fetchall()
column_name_txtan_assessor = [i[0] for i in connx.description]
df_txtan_assessor = pd.DataFrame(df_txtan_assessor, columns=column_name_txtan_assessor)

connx.execute("""
SELECT
    pdc.id_product,                          
	pdc.name_product AS 'PRODUCT',
	comp.competency AS 'COMPETENCY',
	comp.description AS 'COMPETENCY DESCRIPTION',
    lvl.level_name AS 'LEVEL NAME',
    lvl.level_description AS 'LEVEL DESCRIPTION',
    comp.id_competency AS 'id_competency'
FROM `pito_product` AS pdc
JOIN pito_competency AS comp ON comp.id_product = pdc.id_product
LEFT JOIN pito_competency_level AS lvl ON comp.id_competency = lvl.id_competency
""")
df_pito_product = connx.fetchall()
column_names_pito_product = [i[0] for i in connx.description]
df_pito_product = pd.DataFrame(df_pito_product, columns=column_names_pito_product)
options_product_set = [""] + df_pito_product['PRODUCT'].drop_duplicates().tolist() #list produk dari database

connx.execute("""
SELECT
    lvl.name_level AS 'NAMA LEVEL',
    lvl.value_level,
    lvl.id_level_set
FROM pito_level AS lvl;
""")
df_pito_level = connx.fetchall()
column_names_pito_level = [i[0] for i in connx.description]
df_pito_level = pd.DataFrame(df_pito_level, columns=column_names_pito_level)
options_level_set = [""] + df_pito_level['id_level_set'].drop_duplicates().tolist() #list level dari database
connx.close()

st.header("Aplikasi Prediksi Kompetensi")

# Sidebar for navigation
st.sidebar.title("Parameter")
options_num_speaker = [ '2', '1', '3', '4', '5', '6']

#Sidebar
id_input_kode_assessor = st.sidebar.text_input("Kode Assessor Anda")
id_input_id_kandidat = st.sidebar.text_input("ID Kandidat")
selected_base_url = st.sidebar.selectbox("Pilih Sistem:", list(base_urls.keys()))
selected_option_num_speaker = st.sidebar.selectbox("Jumlah Speaker", options_num_speaker)
selected_option_product_set = st.sidebar.selectbox("Set Kompetensi", options_product_set)
selected_option_level_set = st.sidebar.selectbox("Set Level", options_level_set)
        
#connect API kandidat dengan PITO
if id_input_id_kandidat:
    headers = {
        "PITO": {
            "X-API-USER": pito_api_user,
            "X-API-KEY": pito_api_key
        },
        "VAST": {
            "X-API-USER": vast_api_user,
            "X-API-KEY": vast_api_key
        }
    }

    base_url = base_urls[selected_base_url]
    url = f"{base_url}{id_input_id_kandidat}"
    selected_headers = headers[selected_base_url]

    response_id_kandidat = requests.get(url, headers=selected_headers)
    #cek apakah request sukses
    if response_id_kandidat.status_code == 200:
        api_data = response_id_kandidat.json()

        api_id_kandidat = api_data["data"].get('id', 'Tidak tersedia')
        api_nama = api_data["data"].get('name', 'Tidak tersedia')
        api_jenis_kelamin = api_data["data"].get('gender', 'Tidak tersedia')
        api_produk = api_data["data"].get('product', 'Tidak tersedia')
        api_client = api_data["data"].get('client', 'Tidak tersedia')
        api_dob = api_data["data"].get('dob', 'Tidak tersedia')

        with st.container(border=True):
            st.write("#### Informasi ID Kandidat")
            
            st.write(f"ID Kandidat: {api_id_kandidat}")
            st.write(f"Nama: {api_nama}")
            st.write(f"Tanggal Lahir: {api_dob}")
            st.write(f"Jenis Kelamin: {api_jenis_kelamin}")
            st.write(f"Klien: {api_client}")
            st.write(f"Produk: {api_produk}")
    else:
        st.error(f"ID Kandidat tidak terdaftar/Sistem salah")
else:
    st.warning("Silakan masukkan ID Kandidat.")

tab1, tab2, tab3, tab4 = st.tabs(["📈 Input Informasi", "📄 Hasil Transkrip", "🖨️ Hasil Prediksi", "⚙️ <admin> Input"])

########################TAB 1
with tab1:
    if not id_input_kode_assessor: #setting default kalau tidak ada kode assessor
        st.warning("Mohon masukkan kode Assessor Anda.")
    else:
        assessor_row = df_txtan_assessor[df_txtan_assessor['kode_assessor'].str.lower() == id_input_kode_assessor.lower()] #kode assessor bisa besar atau kecil

        if not assessor_row.empty:
            nama_assessor = assessor_row['name_assessor'].values[0]
            st.subheader(f"Selamat Datang, {nama_assessor}")
        else:
            st.subheader("Kode Assessor tidak terdaftar.") #setting kalau kode assessor salah

    #nanti dikasih juga cara dan deskripsi tiap bagian

    #ini nanti pakai API PITO
    # with st.container():
    #     st.markdown('<h2 style="font-size: 24px; font-weight: bold;">Info Kandidat Sesuai ID</h2>', unsafe_allow_html=True)
    #     st.markdown(f'ID Kandidat: {api_id_kandidat}')
    #     st.markdown(f'Name: {api_nama}')
    #     st.markdown(f'Jenis Kelamin: {api_jenis_kelamin}')
    #     st.markdown(f'Produk: {api_produk}')

    selected_product = df_pito_product[df_pito_product["PRODUCT"] == selected_option_product_set]
    with st.container(border=True):
        #Produk yang dipilih
        def get_levels_for_competency(id_competency):
            conn = create_db_connection()
            cursor = conn.cursor()
            
            query = """
                SELECT level_name, level_description
                FROM pito_competency_level
                WHERE id_competency = %s
            """
            cursor.execute(query, (id_competency,))
            results = cursor.fetchall()
            cursor.close()
            conn.close()
            
            levels = [{"level_name": row[0], "level_description": row[1]} for row in results]
            return levels
        
        competency_data = {}
        for _, row in df_pito_product.iterrows():
            if row['PRODUCT'] == selected_option_product_set:
                id_competency = row['id_competency']
                
                if id_competency not in competency_data:
                    competency_data[id_competency] = {
                        "product": row['PRODUCT'],
                        "competency": row['COMPETENCY'],
                        "description": row['COMPETENCY DESCRIPTION'],
                        "levels": []
                    }
                
                if row['LEVEL NAME'] and row['LEVEL DESCRIPTION']:
                    competency_data[id_competency]["levels"].append({
                        "level_name": row['LEVEL NAME'],
                        "level_description": row['LEVEL DESCRIPTION']
                    })

        competency_list = list(competency_data.values())
        
        if not selected_option_product_set:
            st.warning("Silahkan pilih set kompetensi")
        else:
            st.write(f'#### Set Kompetensi dari {selected_option_product_set}')
            if competency_list:
                for competency in competency_list:
                    st.write(f"##### {competency['competency']}")
                    if competency['description']:
                        st.write("Deskripsi:")
                        with st.container(border=True):
                            st.write(f"{competency['description']}")
                    else:
                        st.error('Error: Deskripsi kompetensi tidak ditemukan.', icon="🚨")
                    
                    if competency["levels"]:
                        st.write("Level:")
                        with st.container(border=True):
                            for level in competency["levels"]:
                                st.write(f"{level['level_name']}: {level['level_description']}")
                    else:
                        st.info('Info: Deskripsi level kompetensi tidak ditemukan.', icon="ℹ️")
            else:
                st.write(f"**Kompetensi tidak ditemukan.**")

    selected_level = df_pito_level[df_pito_level['id_level_set'] == selected_option_level_set]
    with st.container(border=True):
        #Level yang dipilih
        if not selected_option_level_set:
            st.warning("Silahkan pilih set level")
        else:
            st.write(f'#### Set Level dari {selected_option_level_set}')
            if not selected_level.empty:
                st.write(f"Terdiri dari:")
                with st.container(border=True):
                    for index, row in selected_level.iterrows():
                        st.write(f"**{row['value_level']}**. {row['NAMA LEVEL']}")
            else:
                st.error(f"Level set tidak ditemukan.", icon="🚨")

    #Tempat upload audio
    st.markdown("Upload File Audio Anda")
    audio_file = st.file_uploader("Pilih File Audio", type=["mp3", "m4a", "wav",])

    # Fungsi untuk mengambil transkrip
    def get_transcriptions(registration_id):
        conn = create_db_connection()
        if conn is None:
            st.error("Failed to connect to the database.")
            return []

        try:
            cursor = conn.cursor()
            query = """
            SELECT t.id_transkrip, t.registration_id, t.transkrip, t.speaker, t.start_section, t.end_section, a.num_speakers
            FROM txtan_transkrip t
            INNER JOIN txtan_audio a ON t.id_audio = a.id_audio
            WHERE a.is_transcribed = %s AND t.registration_id = %s
            """
            # st.write(f"Executing query: {query}") #debug
            cursor.execute(query, (1, registration_id))
            result = cursor.fetchall()
            #st.write(f"Transcriptions fetched: {len(result)}") #debug
            return result

        except Exception as e:
            st.error(f"Transcriptions fetched: {len(result)} for registration_id {registration_id}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    # Fungsi untuk menyimpan ke tabel separator
    def insert_into_separator(id_transkrip, registration_id, revisi_transkrip, revisi_speaker, revisi_start_section, revisi_end_section):
        conn = create_db_connection()
        cursor = conn.cursor()
        query = """
        INSERT INTO txtan_separator (id_transkrip, registration_id, revisi_transkrip, revisi_speaker, revisi_start_section, revisi_end_section)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        values = (id_transkrip, registration_id, revisi_transkrip, revisi_speaker, revisi_start_section, revisi_end_section)
        cursor.execute(query, values)

        #st.write("Inserting into txtan_separator with values:", (id_transkrip, registration_id, revisi_transkrip, revisi_speaker, revisi_start_section, revisi_end_section)) #debug

        conn.commit()
        cursor.close()
        conn.close()

    # Fungsi untuk menyimpan ke tabel result
    def insert_into_result(final_predictions_df, registration_id):
        conn = create_db_connection()
        cursor = conn.cursor()
        query = """
        INSERT INTO txtan_competency_result (registration_id, competency, level, reason)
        VALUES (%s, %s, %s, %s)
        """

        for index, row in final_predictions_df.iterrows():
            competency = row['Kompetensi']
            level = row['Level']
            reason = row['Alasan Kemunculan']

            values = (registration_id, competency, level, reason)
            cursor.execute(query, values)

        # st.write("Inserting into txtan_separator with values:", (registration_id, competency, level, reason)) #debug

        conn.commit()
        cursor.close()
        conn.close()

        st.success("Step 5/5: Prediksi dibuat, proses selesai.") #debug

    # Fungsi untuk mengoreksi label pembicara
    def correct_speaker_labels(transkrip, num_speakers):
        prompt = (
            f"Berikut adalah transkrip dari percakapan interview dari {num_speakers} orang: \n"
            f"{transkrip}\n\n"
            "Dalam transkrip itu masih terdapat overlap antara Kandidat dan Assessor.\n"
            "Maka masukkan bagian yang overlap ke pembicara yang sebenarnya. Sehingga akan ada tanya jawab antar Assessor dan kandidat dan PASTI tidak hanya menjadi satu row.\n "
            "Jika orang lebih dari 2 maka akan ada lebih dari satu assessor. Kandidat tetap hanya akan ada satu.\n"
            "1. Kandidat (yang menjawab pertanyaan)\n"
            "2. Assessor (yang mengajukan pertanyaan)\n"
            "Contoh format dari bagian percakapan assessor dan kandidat:\n"
            "**Kandidat:** Untuk, misalkan contoh produknya ini sudah kita ekspor. Terus sudah kita coba untuk ekspor ke beberapa tempat, bagaimana supaya manajemen distribusinya (MD) itu produk ini dijalankan. Sudah kita ekspor, kita sesuaikan dengan promo yang mereka dari MD berikan. Karena kalau promonya tidak disesuaikan, secara otomatis produk ini nanti tidak akan terjual.\n"
            "**Assessor:** Kemudian, kalau dari sisi improvement, selama dua tahun terakhir ini boleh diceritakan seperti apa langkah improvement yang sudah pernah Bapak coba lakukan dan apakah inisiasinya dari diri Bapak sendiri? Ada contohnya seperti apa? Jika improvement terlalu banyak, seperti yang saya sampaikan tadi, karena kita lebih banyak, kalau saya sendiri.\n"
            "**Kandidat:** Kita lebih banyak ke ATM. Misalkan ada tim di tempat lain melakukan sesuatu, kita coba lakukan itu dengan sedikit modifikasi. Contohnya, kita selalu mengadakan yang namanya Red Light Promo. Itu salah satu usaha yang kita lakukan. Memang itu bukan gagasan dari saya, tapi gagasan dari beberapa toko. Tapi konsistensinya itu saya jalankan di tempat sini, konsistensi sebagaimana kita di tengah kondisi saat ini, contoh, trafik yang turun dan lain-lain, untuk menarik pelanggan yang datang ke toko, baik yang dari mal maupun yang dari luar. Itu yang saya konsistensikan dilakukan di toko ini.\n"
            "**Assessor:** Dengan melihat yang sudah dilakukan di toko-toko lain, jadi coba tetap konsisten dilakukan di tempat saat ini. Kalau misalkan dengan kondisi cabang saat ini, boleh diceritakan?.\n"
            "dan seterusnya.\n"
            "Tolong pastikan urutan dialog tetap seperti dalam transkrip asli, meskipun ada beberapa assessor.\n"
            "Betulkan juga bagian yang ada salah ketik atau ejaan yang kurang benar kecuali nama orang, nama perusahaan, nama jalan, nama kota, nama provinsi, nama negara, nama produk, singkatan.\n"
        )

        messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
            ],
        }
        ]

        try:
            # st.write("Sending request to API...") #debug
            response = openai.chat.completions.create(
                model="o1-mini",
                messages=messages
                # temperature=0,
                # top_p=0.5,
                # frequency_penalty=0,
                # presence_penalty=0
            )

            # st.write("API Response:", response) #debug

            # Validasi respons dari API
            corrected_transcript = response.choices[0].message.content.strip()
            return corrected_transcript
            
        except Exception as e:
            st.error(f"Error while processing: {str(e)}")
            return None
    
    def process_gpt_response_to_dataframe(gpt_response):
        lines = gpt_response.split('\n')
        #st.write(lines) #debug
        data = {'text': [], 'speaker': []}
        #st.write(f"Data pada process gpt response: {data}") #debug

        for line in lines:
            if line.startswith("**Assessor:** ") or line.startswith("Assessor: ") or line.startswith("ASSESSOR: ") or line.startswith("**ASSESSOR**: ") or line.startswith("**ASSESSOR:** "):
                speaker = "Assessor"
                dialogue = line.replace("**Assessor:** ", "").replace("Assessor:", "").replace("ASSESSOR:", "").replace("**ASSESSOR**:", "").replace("**ASSESSOR:**", "").replace("****", "")
            elif line.startswith("**Kandidat:** ") or line.startswith("Kandidat: ") or line.startswith("KANDIDAT: ") or line.startswith("**KANDIDAT**: ") or line.startswith("**KANDIDAT:**"):
                speaker = "Kandidat"
                dialogue = line.replace("**Kandidat:** ", "").replace("Kandidat:", "").replace("KANDIDAT:", "").replace("**KANDIDAT**:", "").replace("**KANDIDAT:**", "").replace("****", "")
            else:
                continue
            data['text'].append(dialogue.strip())
            data['speaker'].append(speaker)
        
        df = pd.DataFrame(data)
        st.success("Step 3/5: Pembicara berhasil ditambahkan.") #debug
        return df

    # Fungsi untuk memproses transkripsi
    def process_transcriptions(registration_id):
        transcriptions = get_transcriptions(registration_id)
        # st.write(transcriptions) #debug

        if not transcriptions:
            st.error("No transcriptions found.")
            return
        
        transcriptions_by_registration = {}

        for transcription in transcriptions:
            reg_id = transcription[1]
            if reg_id not in transcriptions_by_registration:
                transcriptions_by_registration[reg_id] = []
            transcriptions_by_registration[reg_id].append(transcription)

        for registration_id, transcription_group in transcriptions_by_registration.items():
            combined_transcript = "\n".join([f"{t[3]}: {t[2]}" for t in transcription_group])
            num_speakers = transcription_group[0][6]

            #st.write(f"Processing transcription for registration_id {registration_id}")  #debug
            #st.write(combined_transcript) #debug

            corrected_transcript = correct_speaker_labels(combined_transcript, num_speakers)
            #st.write(f"Corrected Transcript: {corrected_transcript}") #debug
            if not corrected_transcript:
                st.error(f"Corrected Transcript is None for registration_id {registration_id}")
                continue

            df = process_gpt_response_to_dataframe(corrected_transcript)
            #st.write(df) #debug
            
            if df.empty:
                st.error(f"Empty DataFrame for registration_id {registration_id}.")
                continue
            
            #st.write(f"Processed DataFrame for {registration_id}:", df)  #debug

            # Merger text dan speaker
            merged_text = []
            merged_speakers = []
            previous_speaker = None
            temp_text = ""
            temp_speaker = ""

            for _, row in df.iterrows():
                current_speaker = row['speaker']
                current_text = row['text']

                if current_speaker == previous_speaker:
                    temp_text += ' ' + current_text
                else:
                    if previous_speaker is not None:
                        merged_text.append(temp_text)
                        merged_speakers.append(temp_speaker)
                    
                    temp_text = current_text
                    temp_speaker = current_speaker
                    previous_speaker = current_speaker

            if temp_text:
                merged_text.append(temp_text)
                merged_speakers.append(temp_speaker)

            df_merged = pd.DataFrame({
                'text': merged_text,
                'speaker': merged_speakers
            })

            df_merged['text'] = df_merged['text'].replace(r'\s+', ' ', regex=True)

            for index, row in df_merged.iterrows():
                #st.write(f"Inserting into txtan_separator: {row['text']}, {row['speaker']}") #debug
                insert_into_separator(
                    transcription_group[0][0], 
                    registration_id, 
                    row['text'], 
                    row['speaker'], 
                    transcription_group[0][4], 
                    transcription_group[0][5]
                )

            #st.success("Transcriptions processed and inserted.") #debug

    def update_transcription_status(id_audio):
        conn = create_db_connection()

        try:
                cursor = conn.cursor()

                update_query = '''
                    UPDATE txtan_audio
                    SET is_transcribed = 1
                    WHERE id_audio = %s
                '''
                cursor.execute(update_query, (id_audio,))
                conn.commit()
                print(f"Audio with id_audio {id_audio} marked as transcribed.")

        except Exception as e:
                print(f"Error: {e}")

    def get_separator(registration_id):
        conn = create_db_connection()
        cursor = conn.cursor()
        query = """
        SELECT s.id_transkrip, s.registration_id, s.revisi_transkrip, s.revisi_speaker, s.revisi_start_section, s.revisi_end_section
        FROM txtan_separator s
        INNER JOIN txtan_audio a ON s.registration_id = a.registration_id
        WHERE a.is_transcribed = 1 AND s.registration_id = %s
        """

        cursor.execute(query, (registration_id,))
        result = cursor.fetchall()

        #st.write(f"Separator data fetched: {len(result)} entries for registration_id {registration_id}") #debug

        cursor.close()
        conn.close()
        return result            
    
    def get_competency(registration_id):
        conn = create_db_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT
                prd.name_product,
                comp.competency,
                comp.description,
                lvl.level_value,
                lvl.level_name,
                lvl.level_description
            FROM txtan_audio a
            JOIN pito_product prd ON prd.id_product = a.id_product
            JOIN pito_competency comp ON comp.id_product = prd.id_product
            LEFT JOIN pito_competency_level lvl ON lvl.id_competency = comp.id_competency
            WHERE a.registration_id = %s
        """
        
        cursor.execute(query, (registration_id,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        #st.write(f"hasil query competency: {competencies}")#debug
        
        # Kembalikan hasil sebagai daftar dictionary agar mudah digunakan
        competencies = [{
            "product": row[0],
            "competency": row[1],
            "description": row[2],
            "level_value": row[3],
            "level_name": row[4],
            "level_description": row[5]
        } for row in result]
        
        return competencies

    def get_level_set_from_audio_table(registration_id):
            query = """
            SELECT a.id_level_set, lvl.name_level AS 'NAMA LEVEL'
            FROM txtan_audio a
            JOIN pito_level lvl ON a.id_level_set = lvl.id_level_set
            WHERE a.registration_id = %s AND a.is_transcribed = 1
            """
            conn = create_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute(query, (registration_id,))
                result = cursor.fetchone()
                cursor.fetchall()
                return result if result else (None, None)
            except Exception as e:
                print(f"Error fetching level set: {e}")
                return None, None
            finally:
                cursor.close()
                conn.close()

    id_level_set_fix, nama_level = get_level_set_from_audio_table(id_input_id_kandidat)
    filtered_levels_predict_competency = df_pito_level[df_pito_level['id_level_set'] == id_level_set_fix]
    dropdown_options_predict_competency = filtered_levels_predict_competency['NAMA LEVEL'].tolist()
    #st.write(dropdown_options_predict_competency)#debug

    def predict_competency(combined_text, competencies):
        prompt = "Saya memiliki transkrip hasil dari wawancara dan daftar kompetensi yang ingin diidentifikasi.\n\n"
        prompt += "Buatlah hasil analisa menjadi bentuk tabel dan prediksi juga levelnya.\n"
        prompt += "Hasil yang dikeluarkan WAJIB table dan TANPA FORMAT TEXT bold, italic atau sejenisnya.\n"
        prompt += "Level yang digunakan adalah Very High, High, Medium, Low, Very Low dan level WAJIB dalam bahasa inggris.\n"
        #prompt += f"Level yang digunakan juga mengikuti dari {dropdown_options_predict_competency} dan level WAJIB dalam bahasa inggris.\n"
        prompt += f"Teks transkrip berikut: {combined_text}\n\n"
        prompt += "Berikut adalah daftar kompetensi dengan level dan deskripsinya:\n"
        
        for competency in competencies:
            prompt += (f"- Kompetensi: {competency['competency']}\n"
                    f"  Deskripsi Kompetensi (umum): {competency['description']}\n")
            
            if competency.get("levels"):
                prompt += "  Level:\n"
                for level in competency["levels"]:
                    level_description = level["level_description"] if level["level_description"] else competency['description']
                    prompt += (f"    - Name: {level['level_name']}\n"
                            f"      Deskripsi Level: {level_description}\n")
            else:
                prompt += f"  (Tidak ada level spesifik, gunakan deskripsi kompetensi umum: {competency['description']})\n"
                prompt += "Level yang digunakan adalah Very High, High, Medium, Low, Very Low dan level WAJIB dalam bahasa inggris.\n"
                #prompt += f" Serta level mengikuti dari {dropdown_options_predict_competency}."

        prompt += "\nHasil hanya akan berupa tabel dengan kolom: Kompetensi, Level, dan Alasan Kemunculan\n"
        
        #st.write(f"Prompt: {prompt}") #debug

        messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": prompt
                },
            ],
        }
        ]

        response = openai.chat.completions.create(
            model="o1-mini",
            messages = messages
            # temperature=0,
            # top_p=0.5,
            # frequency_penalty=0,
            # presence_penalty=0
        )

        corrected_transcript_dict = response.model_dump()
        corrected_transcript = corrected_transcript_dict['choices'][0]['message']['content']
        return corrected_transcript

    def combine_text_by_registration(separator_data):
        combined_data = defaultdict(lambda: {"revisi_transkrip": "", "revisi_speaker": ""})

        for record in separator_data:
            registration_id = record[1] #ini kuraang yakin harusnya dimulai dari 0 atau 1, nanti di cek
            revisi_transkrip = record[2] or ""
            revisi_speaker = record[3] or ""

            combined_data[registration_id]["revisi_transkrip"] += f" {revisi_transkrip}"
            combined_data[registration_id]["revisi_speaker"] += f" {revisi_speaker}"

        return combined_data

    def predictor(registration_id):
        # Ambil data revisi dan kompetensi
        separator_data = get_separator(registration_id)
        #st.write(f"Separator data: {separator_data}") #debug
        competency_data = get_competency(registration_id)
        #st.write(f"Competency data: {competency_data}") #debug

        #st.write(f"Fetched {len(separator_data)} separator data entries") #debug
        #st.write(f"Fetched {len(competency_data)} competency data entries") #debug

        if not separator_data:
            st.error("No data found in the separator table.")
            return

        if not competency_data:
            st.error("No competency data found.")
            return

        competency_list = [{"competency": row.get("competency"), 
                            "description": row.get("description"),
                            **({
                                "level_value": row.get("level_value"),
                                "level_name": row.get("level_name"),
                                "level_description": row.get("level_description")
                                }if row.get("level_value") and row.get("level_name") and row.get("level_description") else {})
                            } 
                            for row in competency_data]
        #st.write(f"Competency list: {competency_list}") #debug

        combined_data = combine_text_by_registration(separator_data)
        #st.write(f"combined_data: {combined_data}") #debug

        all_predictions = []

        for registration_id, text_data in combined_data.items():
            combined_text = f"{text_data['revisi_transkrip']} {text_data['revisi_speaker']}"

            # st.success(f"Step 4/5: Mohon tunggu, proses prediksi berlangsung.....") #debug

            predicted_competency = predict_competency(combined_text, competency_list)

            #st.write(f"Predicted competency for {registration_id}:\n{predicted_competency}") #debug

            try:
                df_competency = pd.read_csv(StringIO(predicted_competency), sep='|', skipinitialspace=True)
                df_competency.columns = df_competency.columns.str.strip()
                df_competency['registration_id'] = registration_id
                st.success(f"Step 4/5: Mohon tunggu, proses prediksi berlangsung.....") #debug

                all_predictions.append(df_competency)

            except Exception as e:
                st.error(f"Error processing prediction for registration ID {registration_id}: {e}")
        
        #st.write(all_predictions) #debug

        if all_predictions:
            #st.write(f"all_predictions before: {all_predictions}")  # debug
            
            if isinstance(all_predictions, list) and all(isinstance(df, pd.DataFrame) for df in all_predictions):
                final_predictions_df = pd.concat(all_predictions, ignore_index=True)
                #st.dataframe(f"Final pred CONCAT: {final_predictions_df}") #debug
                final_predictions_df = final_predictions_df.applymap(lambda x: x.replace('**', '') if isinstance(x, str) else x)
                #st.dataframe(f"Final pred MAP: {final_predictions_df}") #debug
                final_predictions_df = final_predictions_df.drop(index=0).reset_index(drop=True)
                #st.dataframe(f"Final pred DROP dan RESET INDEX: {final_predictions_df}") #debug
                
                #st.write(f"Final pred DONE: {final_predictions_df}")  # debug
                
                insert_into_result(final_predictions_df, registration_id)
            else:
                st.error("Error: all_predictions harus berupa list yang berisi DataFrame.")
        else:
            st.error("Error: all_predictions kosong.")

    if st.button("Upload, Transcribe dan Prediksi", key="SimpanTranscribe"):
        if audio_file is not None:
            s3_client = boto3.client('s3',
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key,
                        endpoint_url=endpoint_url)
            
            bucket_name = 'rpi-ta'
            file_name = audio_file.name

            audio_file_copy = io.BytesIO(audio_file.getvalue()) 

            try:
                s3_client.upload_fileobj(audio_file, bucket_name, file_name)
                st.success(f"Step 1/5: File {file_name} berhasil terupload.")
            except Exception as e:
                st.error(f"Error saat upload ke S3: {e}")
                st.stop()

            tz = pytz.timezone('Asia/Jakarta')

            try:
                cursor = conn.cursor()
                selected_id_product = int(selected_product['id_product'].iloc[0])
                selected_option_num_speaker = int(selected_option_num_speaker)
                insert_query = """
                INSERT INTO txtan_audio (registration_id, date, num_speakers, id_product, id_level_set, kode_assessor, audio_file_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                data = (
                    id_input_id_kandidat,
                    datetime.now(tz),
                    selected_option_num_speaker,
                    selected_id_product,
                    selected_option_level_set,
                    id_input_kode_assessor,
                    file_name
                )
                cursor.execute(insert_query, data)
                conn.commit()
                id_audio = cursor.lastrowid
                # st.success("Informasi berhasil tersimpan ke database.") #debug
            except Exception as e:
                st.error(f"Error saat menyimpan ke database: {e}")
                st.stop()
            finally:
                cursor.close()

            try:
                files = {'file': (file_name, audio_file_copy.getvalue(), 'audio/wav')}
                data = {'registration_id': id_input_id_kandidat}
		    keepalive = {"Connection": "keep-alive"}
                response = requests.post(f"{flask_url}/transcribe", files=files, headers=keepalive, data=data, timeout=600)
                
                if response.status_code == 200:
                    st.success("Step 2/5: Audio berhasil ditranskripsi.") #debug
                    segments = response.json() 

                    if segments:
                        for segment in segments:
                            registration_id = segment['registration_id']
                            text = segment['transcript']
                            speaker = segment['speaker']
                            start_section = segment['start_section']
                            end_section = segment['end_section']

                            #st.write(f"Registration ID: {registration_id}, ID Audio: {id_audio}, Speaker: {speaker}") #debug

                            try:
                                cursor = conn.cursor()
                                insert_transcript_query = """
                                INSERT INTO txtan_transkrip (registration_id, id_audio, start_section, end_section, transkrip, speaker)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                """

                                data_transcript = (
                                    registration_id,
                                    id_audio,
                                    start_section,
                                    end_section,
                                    text,
                                    speaker
                                )

                                cursor.execute(insert_transcript_query, data_transcript)
                                conn.commit()

                                update_transcription_status(id_audio)
                            except Exception as e:
                                st.error(f"Error saat menyimpan transkrip ke database: {e}")
                            finally:
                                cursor.close()

                    else:
                        st.error("No segments found in the response.")
                else:
                    st.error(f"Error saat memanggil API transkripsi: {response.content}")
                
                #st.write("transkrip bermasalah") #debug
                process_transcriptions(id_input_id_kandidat)
                #st.write("prediktor bermasalah") #debug
                predictor(id_input_id_kandidat)
            
            except Exception as e:
                st.error(f"Error setelah predictor: {e}")

            finally:
                cursor.close()
                conn.close()

########################TAB 2
with tab2:
    # with st.container():
    #     st.markdown('<h2 style="font-size: 24px; font-weight: bold;">Info Kandidat Sesuai ID</h2>', unsafe_allow_html=True)
    #     st.markdown(f'ID Kandidat: {api_id_kandidat}')
    #     st.markdown(f'Name: {api_nama}')
    #     st.markdown(f'Jenis Kelamin: {api_jenis_kelamin}')
    #     st.markdown(f'Produk: {api_produk}')

    with st.container():
        def get_transkrip_data(registration_id):
            conn = create_db_connection()
            if conn is None:
                st.error("Database connection not available.")
                return pd.DataFrame(columns=["Start", "End", "Transkrip", "Speaker"])

            try:
                cursor = conn.cursor()
                query = """
                SELECT revisi_start_section AS 'Start', revisi_end_section AS 'End', revisi_transkrip AS 'Transkrip', revisi_speaker AS 'Speaker'
                FROM txtan_separator
                WHERE registration_id = %s
                """
                cursor.execute(query, (registration_id,))
                result = cursor.fetchall()
                cursor.close()
                conn.close()

                if result:
                    df = pd.DataFrame(result, columns=["Start", "End", "Transkrip", "Speaker"]) #start dan end masihh dalam sec
                    return df
                else:
                    return pd.DataFrame(columns=["Start", "End", "Transkrip", "Speaker"])

            except mysql.connector.Error as e:
                st.error(f"Error fetching transcription data: {e}")
                return pd.DataFrame(columns=["Start", "End", "Transkrip", "Speaker"])
            finally:
                if conn.is_connected():
                    conn.close()
        
        if id_input_id_kandidat:
            df_transkrip = get_transkrip_data(id_input_id_kandidat)
            df_transkrip_reset = df_transkrip.reset_index(drop=True)
            table_html = df_transkrip_reset.to_html(index=False, escape=False)
            st.markdown("""
                <style>
                table {
                    width: 100%;
                    border-collapse: collapse;
                }
                th, td {
                    text-align: left;
                    vertical-align: top;
                    padding: 8px;
                    border: 1px solid #ddd;
                    word-wrap: break-word;
                    white-space: pre-wrap;
                }
                th {
                    background-color: #00;
                }
                </style>
            """, unsafe_allow_html=True)
            st.markdown(table_html, unsafe_allow_html=True)
        else:
            st.warning("ID Kandidat tidak ditemukan/kosong")

########################TAB 3
with tab3:
    # with st.container():
    #     st.markdown('<h2 style="font-size: 24px; font-weight: bold;">Info Kandidat Sesuai ID</h2>', unsafe_allow_html=True)
    #     st.markdown(f'ID Kandidat: {api_id_kandidat}')
    #     st.markdown(f'Name: {api_nama}')
    #     st.markdown(f'Jenis Kelamin: {api_jenis_kelamin}')
    #     st.markdown(f'Produk: {api_produk}')

    def get_result_data(registration_id):
        query = """
        SELECT competency, level, reason
        FROM txtan_competency_result
        WHERE registration_id = %s
        """
        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute(query, (registration_id,))
        result = cursor.fetchall()

        cursor.close()

        if result:
            df = pd.DataFrame(result, columns=["competency", "level", "reason"])
            return df
        else:
            return pd.DataFrame(columns=["competency", "level", "reason"])
        
    def get_all_so_values(registration_id):
        conn = create_db_connection()
        try:
            cursor = conn.cursor()
            query = """
            SELECT competency, so_level, so_reason
            FROM txtan_competency_result
            WHERE registration_id = %s
            """
            cursor.execute(query, (registration_id,))
            return cursor.fetchall() 
        except mysql.connector.Error as e:
            print(f"Database error: {e}")
            return []  
        finally:
            cursor.close()
            conn.close()

    def update_single_entry_db(conn, competency, level, reason, so_level, so_reason, registration_id):
        try:
            cursor = conn.cursor()
            
            # Handle None values for so_level and so_reason
            so_level = so_level if so_level != '' else None
            so_reason = so_reason if so_reason != '' else None

            # Check if the record already exists
            check_query = """
            SELECT COUNT(*) FROM txtan_competency_result
            WHERE registration_id = %s AND competency = %s AND level = %s AND reason = %s
            """
            cursor.execute(check_query, (registration_id, competency, level, reason))
            count = cursor.fetchone()[0]

            # Update or insert the record
            if count > 0:
                update_query = """
                UPDATE txtan_competency_result
                SET so_level = %s, so_reason = %s
                WHERE registration_id = %s AND competency = %s AND level = %s AND reason = %s
                """
                cursor.execute(update_query, (so_level, so_reason, registration_id, competency, level, reason))
            else:
                insert_query = """
                INSERT INTO txtan_competency_result (registration_id, competency, level, reason, so_level, so_reason)
                VALUES (%s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (registration_id, competency, level, reason, so_level, so_reason))

            conn.commit()

        except Exception as e:
            print(f"Error updating or inserting entry: {e}")
        finally:
            cursor.close()
    
    with st.container(border=True):
        st.write("Pilihan 'kosong' ada bisa dipilih jika dirasa memang tidak muncul di Assessor")
        st.write("Dropdown kompetensi dan level kompetensi **di sidebar** tidak akan mengubah pilihan level di bagian ini")

    with st.container():
        if id_input_id_kandidat:
            df_result_prediction = get_result_data(id_input_id_kandidat)

            if 'original_results' not in st.session_state:
                st.session_state['original_results'] = df_result_prediction.copy()

            df_result_prediction = st.session_state['original_results']

            id_level_set_fix, nama_level = get_level_set_from_audio_table(id_input_id_kandidat)

            filtered_levels = df_pito_level[df_pito_level['id_level_set'] == id_level_set_fix]
            dropdown_options = filtered_levels['NAMA LEVEL'].tolist()
            dropdown_options.insert(0, '')

            so_values = get_all_so_values(id_input_id_kandidat)
            so_dict = {comp[0]: (comp[1], comp[2]) for comp in so_values}

            # Initialize a dictionary to track changes for save
            changes_to_save = []

            for i, row in enumerate(df_result_prediction.itertuples()):
                st.markdown(f"##### {row.competency}")
                st.write(f"###### Level: {row.level}")
                st.write(f"###### Alasan muncul: {row.reason}")

                so_level_key = f"dropdown_{i}"
                so_reason_key = f"text_input_{i}"

                current_so_level_value, current_so_reason_value = so_dict.get(row.competency, ("", ""))

                if f"prev_so_level_{i}" not in st.session_state:
                    st.session_state[f"prev_so_level_{i}"] = current_so_level_value
                if f"prev_so_reason_{i}" not in st.session_state:
                    st.session_state[f"prev_so_reason_{i}"] = current_so_reason_value

                so_level = st.selectbox(
                    f"SO Level {row.competency}", 
                    dropdown_options, 
                    key=so_level_key,
                    index=dropdown_options.index(current_so_level_value) if current_so_level_value in dropdown_options else 0
                )

                so_reason = st.text_area(
                    f"Keterangan (opsional)", 
                    value=current_so_reason_value if current_so_reason_value else "",
                    key=f"so_reason_{row.competency}_{i}"
                )

                # Only track changes in session state, do not update the DB immediately
                if (so_level != st.session_state[f"prev_so_level_{i}"]) or (so_reason != st.session_state[f"prev_so_reason_{i}"]):
                    # Save the changes to be updated later
                    changes_to_save.append((row.competency, row.level, row.reason, so_level, so_reason, id_input_id_kandidat))
                    st.session_state[f"prev_so_level_{i}"] = so_level
                    st.session_state[f"prev_so_reason_{i}"] = so_reason

            # Add a "Save" button at the end
            if st.button("Save Changes"):
                if changes_to_save:
                    try:
                        # Connect to the DB and update the records
                        conn = create_db_connection()
                        for change in changes_to_save:
                            competency, level, reason, so_level, so_reason, registration_id = change
                            update_single_entry_db(conn, competency, level, reason, so_level, so_reason, registration_id)
                        st.success("Perubahan berhasil disimpan!")
                    except Exception as e:
                        st.error(f"Error saving changes: {e}")
                else:
                    st.warning("Perubahan yang Anda lakukan sama dengan yang sudah disimpan")
        else:
            st.warning("ID Kandidat tidak ditemukan/kosong")

########################TAB 4
with tab4:
    with st.container(border=True):
        st.write("Berikut adalah fitur dimana Anda bisa menambahkan parameter ke sistem")

    subtab1, subtab2, subtab3 = st.tabs(["⚙️ <admin> Input Produk", "⚙️ <admin> Input Level", "⚙️ <admin> Input Assessor"])

    ########################SUBTAB 1
    with subtab1:
        if 'competencies' not in st.session_state:
            st.session_state['competencies'] = []

        def save_competencies_to_db(id_product):
            conn = create_db_connection()
            cursor = conn.cursor()

            query_find_competency = """
                SELECT id_competency FROM pito_competency WHERE competency = %s
            """
            query_insert_competency = """
                INSERT INTO pito_competency (id_product, competency, description) 
                VALUES (%s, %s, %s)
            """
            query_find_level = """
                SELECT id_pito_competency_level FROM pito_competency_level 
                WHERE id_competency = %s AND level_value = %s
            """
            query_insert_level = """
                INSERT INTO pito_competency_level (level_value, level_name, level_description, id_competency) 
                VALUES (%s, %s, %s, %s)
            """

            for competency, description, levels in st.session_state['competencies']:
                cursor.execute(query_find_competency, (competency,))
                result = cursor.fetchone()

                if result:
                    id_competency = result[0]
                else:
                    cursor.execute(query_insert_competency, (id_product, competency, description))
                    conn.commit()
                    id_competency = cursor.lastrowid  

                for level in levels:
                    cursor.execute(query_find_level, (id_competency, level["value"]))
                    level_exists = cursor.fetchone()

                    if not level_exists:
                        cursor.execute(query_insert_level, (
                            level["value"],
                            level["name"],
                            level["description"],
                            id_competency
                        ))
                    else:
                        st.warning(f"Level Value '{level['value']}' sudah ada untuk kompetensi '{competency}' dan tidak akan ditambahkan lagi.")

            conn.commit()
            cursor.close()
            conn.close()

        def is_product_exists(product_name):
            conn = create_db_connection()
            cursor = conn.cursor()
            
            query_check = """
                SELECT COUNT(*) FROM pito_product WHERE name_product = %s
            """
            cursor.execute(query_check, (product_name,))
            exists = cursor.fetchone()[0] > 0
            
            cursor.close()
            conn.close()
            
            return exists

        with st.form(key='input_form'):
            input_name_product = st.text_input('Name Product', key='name_product')

            temp_competency = st.text_input('Competency', key='input_competency_temp')
            temp_description = st.text_area('Description', key='input_description_temp')

            level_value = st.number_input('Level Value', step=1, key='level_value')
            level_name = st.text_input('Level Name', key='level_name')
            level_description = st.text_area('Level Description', key='level_description')

            if st.form_submit_button(label='Add Competency Level'):
                if level_name and level_description:
                    if 'competency_levels' not in st.session_state:
                        st.session_state['competency_levels'] = []
                    st.session_state['competency_levels'].append({
                        "value": level_value,
                        "name": level_name,
                        "description": level_description,
                    })
                    st.success(f"Level kompetensi '{level_name}' ditambahkan.")

            if st.form_submit_button(label='Add Competency'):
                if temp_competency and temp_description:
                    if 'competencies' not in st.session_state:
                        st.session_state['competencies'] = []
                    st.session_state['competencies'].append((temp_competency, temp_description, st.session_state.get('competency_levels', [])))
                    st.success(f"Competency '{temp_competency}' ditambahkan.")
                    st.session_state['competency_levels'] = []
            
            st.write("Competencies yang sudah ditambahkan:")
            for idx, (competency, description, levels) in enumerate(st.session_state['competencies']):
                st.write(f"{idx + 1}. Competency: {competency}, Description: {description}")
                if levels:
                    for level in levels:
                        st.write(f"    - Level Value: {level['value']}, Level Name: {level['name']}, Level Description: {level['description']}")

            submit_button = st.form_submit_button(label='Submit')

        if submit_button:
            if input_name_product:  
                if is_product_exists(input_name_product):
                    st.error(f"Nama produk '{input_name_product}' sudah ada. Mohon gunakan nama lain.")
                else:
                    try:
                        conn = create_db_connection()
                        cursor = conn.cursor()
                        
                        query_product = """
                            INSERT INTO pito_product (name_product) 
                            VALUES (%s)
                        """
                        cursor.execute(query_product, (input_name_product,))
                        conn.commit()  

                        id_product = cursor.lastrowid

                        save_competencies_to_db(id_product)

                        st.success("Data produk, kompetensi, dan level kompetensi berhasil dimasukkan!")
                    except Exception as e:
                        st.error(f"Error saat menyimpan data: {e}")
                    finally:
                        cursor.close()
                        conn.close()
            else:
                st.error("Mohon masukkan nama produk sebelum menyimpan.")
                

    ########################SUBTAB 2
    with subtab2:
        if 'new_levels_name' not in st.session_state:
            st.session_state['new_levels_name'] = []
        if 'new_levels_value' not in st.session_state:
            st.session_state['new_levels_value'] = []

        with st.container(border=True):
            def save_level_set_to_db(level_set_name, levels_name, levels_value):
                conn = create_db_connection()
                cursor = conn.cursor()

                try:
                    query_check_existing = """
                        SELECT COUNT(*)
                        FROM pito_level 
                        WHERE id_level_set = %s
                    """

                    cursor.execute(query_check_existing, (level_set_name,))
                    existing_count = cursor.fetchone()[0]

                    if existing_count > 0:
                        st.error(f"{level_set_name} sudah ada, mohon gunakan nama lain")
                        return

                    query_insert_level = """
                        INSERT INTO pito_level (name_level, value_level, id_level_set)
                        VALUES (%s, %s, %s)
                    """
                    for name, value in zip(levels_name, levels_value):
                        cursor.execute(query_insert_level, (name, value, level_set_name))
                    
                    conn.commit()
                
                except Exception as e:
                    st.error(f"Error saat menyimpan level set: {e}")
                
                finally:
                    cursor.close()
                    conn.close()

            def get_existing_levels(level_set_name):
                conn = create_db_connection()
                cursor = conn.cursor()

                query = """
                    SELECT name_level, value_level
                    FROM pito_level
                    WHERE id_level_set = %s
                """

                cursor.execute(query, (level_set_name,))
                result = cursor.fetchall()
                cursor.close()
                conn.close()

                return result

            level_set_name = st.text_input("Nama Level Set Baru", key="tab5_level_set")

            if level_set_name:
                existing_levels = get_existing_levels(level_set_name)
                if existing_levels:
                    st.warning(f"Set level '{level_set_name}' sudah ada, menampilkan level yang sudah ada.")
                    if not st.session_state['new_levels_name']: 
                        for name, value in existing_levels:
                            st.session_state['new_levels_name'].append(name)
                            st.session_state['new_levels_value'].append(value)

            input_level_name = st.text_input("Nama Level", key="tab5_nama_level")
            input_level_number = st.number_input("Masukkan Value Level", key="tab5_value_level", step=1)

            if st.button("Add Level", key="button_add_level"):
                if input_level_name and input_level_number:
                    if input_level_name in st.session_state['new_levels_name']:
                        st.error(f"Level dengan nama '{input_level_name}' sudah ada.")
                    else:
                        st.session_state['new_levels_name'].append(input_level_name)
                        st.session_state['new_levels_value'].append(input_level_number)
                        st.success(f"Level {input_level_name} dengan value {input_level_number} ditambahkan.")
                else:
                    st.error("Mohon masukkan nama level dan value level sebelum menambahkannya.")

            if st.session_state['new_levels_name']:
                st.write("Level yang sudah ditambahkan:")
                for i, (name, value) in enumerate(zip(st.session_state['new_levels_name'], st.session_state['new_levels_value'])):
                    st.write(f"{i+1}. Nama Level: {name}, Value Level: {value}")

                    if st.button(f"Hapus Level {name}", key=f"delete_{i}"):
                        st.session_state['new_levels_name'].pop(i)
                        st.session_state['new_levels_value'].pop(i)
                        st.success(f"Level '{name}' berhasil dihapus.")
                        st.experimental_rerun() 
            
            if st.button("Simpan Set Kompetensi", key="save_level"):
                if level_set_name and st.session_state['new_levels_name']:
                    
                    save_level_set_to_db(level_set_name, st.session_state['new_levels_name'], st.session_state['new_levels_value'])
                    
                    st.session_state['new_levels_name'] = []
                    st.session_state['new_levels_value'] = []
                    st.success("Set level berhasil ditambahkan!")
                else:
                    st.error("Mohon masukkan nama set level dan setidaknya satu level sebelum menyimpan.")

    ########################TAB 6
    with subtab3:
        st.write('Input Assessor')

        def get_existing_assessor(assessor_code):
            conn = create_db_connection()
            cursor = conn.cursor()

            query = """
                SELECT kode_assessor, name_assessor
                FROM txtan_assessor
                WHERE kode_assessor = %s
            """

            cursor.execute(query, (assessor_code,))
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            return result
        
        def save_assessor_to_db(assessor_code, name_assessor):
            conn = create_db_connection()
            cursor = conn.cursor()

            try:
                existing_assessor = get_existing_assessor(assessor_code)

                if existing_assessor:
                    existing_name_assessor = existing_assessor[1]
                    st.error(f'Assessor dengan kode {assessor_code} sudah digunakan oleh {existing_name_assessor}, mohon gunakan kode lain.')
                    return

                query_insert_assessor = """
                INSERT INTO txtan_assessor (kode_assessor, name_assessor)
                VALUES (%s, %s)
                """
                cursor.execute(query_insert_assessor, (assessor_code, name_assessor))
                conn.commit()
                st.success(f"Assessor {name_assessor} dengan kode {assessor_code} berhasil disimpan")

            except Exception as e:
                st.error(f"Error saat menyimpan kode assessor: {e}")

            finally:
                cursor.close()
                conn.close()

        input_assessor_code = st.text_input("Kode Assessor (Huruf Kapital)")
        input_assessor_name = st.text_input("Nama Assessor")

        if st.button("Simpan Assessor"):
            if input_assessor_code and input_assessor_name:
                save_assessor_to_db(input_assessor_code, input_assessor_name)
            else:
                st.error("Mohon masukkan kode dan nama assessor.")





