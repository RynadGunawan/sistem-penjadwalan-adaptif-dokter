import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta

# Fungsi untuk perhitungan kriteria gangguan
def hitung_kriteria(row):
    if row['Pasien per Peserta Didik'] > 18:
        return 'Overloaded'
    elif row['Pasien per Peserta Didik'] < 8:
        return 'Underutilized'
    else:
        return 'Normal'

# Fungsi penjadwalan awal
def generate_initial_schedule(df):
    df['Tanggal'] = pd.to_datetime(df['Tanggal']).dt.date
    df['Pasien per Peserta Didik'] = (df['Total Pasien'] / df['Peserta Didik'].replace(0, 1)).astype(int)
    df['Kriteria Gangguan'] = df.apply(hitung_kriteria, axis=1)
    return df

# Fungsi optimisasi berdasarkan tanggal yang dipilih
def optimize_schedule(df, df_peserta, selected_date):
    # Filter data berdasarkan tanggal yang dipilih
    df_date = df[df['Tanggal'] == selected_date].copy()
    df_opt = df.copy()
    df_peserta_opt = df_peserta.copy()
    
    # Hitung kebutuhan ideal peserta didik untuk data tanggal yang dipilih
    df_date['Peserta Ideal'] = (df_date['Total Pasien'] / 13).round().astype(int)
    df_date['Peserta Ideal'] = df_date['Peserta Ideal'].clip(lower=1, upper=df_date['Kapasitas'])
    
    # Hitung surplus/defisit
    df_date['Surplus/Defisit'] = df_date['Peserta Didik'] - df_date['Peserta Ideal']
    
    # Buat daftar untuk tracking perubahan penempatan
    relokasi_mahasiswa = []
    
    # Dapatkan data RS dengan surplus dan defisit
    surplus_rs = df_date[df_date['Surplus/Defisit'] > 0]
    defisit_rs = df_date[df_date['Surplus/Defisit'] < 0]
    
    for _, defisit_row in defisit_rs.iterrows():
        kebutuhan = abs(defisit_row['Surplus/Defisit'])
        target_rs = defisit_row['Nama Wahana']
        tanggal = defisit_row['Tanggal']
        
        for _, surplus_row in surplus_rs.iterrows():
            if kebutuhan <= 0:
                break
                
            source_rs = surplus_row['Nama Wahana']
            available = min(surplus_row['Surplus/Defisit'], kebutuhan)
            
            if available <= 0:
                continue
                
            # Dapatkan mahasiswa yang akan direlokasi
            mahasiswa_untuk_relokasi = df_peserta_opt[
                (df_peserta_opt['Penempatan RS'] == source_rs) & 
                (df_peserta_opt['Tanggal'] == tanggal)
            ].head(int(available))
            
            # Update penempatan mahasiswa
            for idx in mahasiswa_untuk_relokasi.index:
                nama_mahasiswa = df_peserta_opt.at[idx, 'Nama Peserta']
                df_peserta_opt.at[idx, 'Penempatan RS'] = target_rs
                relokasi_mahasiswa.append({
                    'Nama': nama_mahasiswa,
                    'Dari': source_rs,
                    'Ke': target_rs,
                    'Tanggal': tanggal
                })
            
            # Update surplus/defisit
            surplus_rs.loc[surplus_rs['Nama Wahana'] == source_rs, 'Surplus/Defisit'] -= available
            kebutuhan -= available
    
    # Update jumlah peserta didik berdasarkan data yang dioptimasi
    for wahana in df_opt['Nama Wahana'].unique():
        jumlah_peserta = len(df_peserta_opt[
            (df_peserta_opt['Penempatan RS'] == wahana) & 
            (df_peserta_opt['Tanggal'] == tanggal)
        ])
        df_opt.loc[(df_opt['Nama Wahana'] == wahana) & (df_opt['Tanggal'] == tanggal), 'Peserta Didik'] = jumlah_peserta
    
    # Recalculate metrik
    df_opt['Pasien per Peserta Didik'] = (df_opt['Total Pasien'] / df_opt['Peserta Didik'].replace(0, 1)).astype(int)
    df_opt['Kriteria Gangguan'] = df_opt.apply(hitung_kriteria, axis=1)
    
    return df_opt, df_peserta_opt, relokasi_mahasiswa

# Streamlit App
st.set_page_config(page_title="Penjadwalan Adaptif Dokter", layout="wide")

with st.sidebar:
    st.header("Upload Data")
    uploaded_file = st.file_uploader("Upload file Excel", type=["xlsx"])
    if uploaded_file:
        # Baca kedua sheet
        df_wahana = pd.read_excel(uploaded_file, sheet_name='dummy_wahana_data')
        df_peserta = pd.read_excel(uploaded_file, sheet_name='data_peserta')
        
        # Pastikan df_peserta memiliki kolom Tanggal
        if 'Tanggal' not in df_peserta.columns:
            # Duplikasi data mahasiswa untuk beberapa tanggal sebagai contoh
            dates = df_wahana['Tanggal'].unique()
            all_peserta = []
            for date in dates:
                temp_df = df_peserta.copy()
                temp_df['Tanggal'] = pd.to_datetime(date).date()
                all_peserta.append(temp_df)
            df_peserta = pd.concat(all_peserta, ignore_index=True)
        else:
            df_peserta['Tanggal'] = pd.to_datetime(df_peserta['Tanggal']).dt.date
        
        df_wahana = generate_initial_schedule(df_wahana)
        st.session_state['df_wahana'] = df_wahana
        st.session_state['df_peserta'] = df_peserta
        st.session_state['is_optimized'] = False
        st.session_state['tanggal_tersedia'] = sorted(df_wahana['Tanggal'].unique())

st.title("🩺 Sistem Penjadwalan Adaptif Peserta Didik Profesi Dokter")

if 'df_wahana' in st.session_state and 'df_peserta' in st.session_state:
    df = st.session_state['df_wahana']
    df_peserta = st.session_state['df_peserta']
    tanggal_tersedia = st.session_state['tanggal_tersedia']
    
    # Pilih tanggal untuk melihat data
    selected_date = st.selectbox(
        "📅 Pilih Tanggal",
        options=tanggal_tersedia,
        format_func=lambda x: x.strftime('%d %B %Y')
    )
    
    # Filter data berdasarkan tanggal
    df_selected_date = df[df['Tanggal'] == selected_date]
    
    # Pilih wahana untuk melihat data peserta
    st.subheader("👥 Daftar Peserta Didik per Wahana")
    
    selected_wahana_peserta = st.selectbox(
        "Pilih Wahana untuk Melihat Peserta", 
        df_selected_date['Nama Wahana'].unique()
    )
    
    # Filter dan tampilkan data
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            label="Total Peserta Didik", 
            value=int(df_selected_date[df_selected_date['Nama Wahana'] == selected_wahana_peserta]['Peserta Didik'].values[0]),
            help="Jumlah peserta didik yang aktif di wahana ini"
        )
    
    with col2:
        # Tampilkan peserta sesuai status optimasi
        if 'is_optimized' in st.session_state and st.session_state['is_optimized']:
            peserta_wahana = st.session_state['df_peserta_opt'][
                (st.session_state['df_peserta_opt']['Penempatan RS'] == selected_wahana_peserta) & 
                (st.session_state['df_peserta_opt']['Tanggal'] == selected_date)
            ]
        else:
            peserta_wahana = df_peserta[
                (df_peserta['Penempatan RS'] == selected_wahana_peserta) & 
                (df_peserta['Tanggal'] == selected_date)
            ]
        
        # Tambahkan kolom nomor untuk indeks mulai dari 1
        peserta_wahana = peserta_wahana.reset_index(drop=True)
        peserta_wahana.index = peserta_wahana.index + 1
        
        st.dataframe(
            peserta_wahana[['Nama Peserta']],
            height=200,
            use_container_width=True,
            column_config={"Nama Peserta": "Daftar Nama Peserta"}
        )

    # Tampilan Data Utama
    st.subheader(f"📋 Data Penjadwalan RS")
    color_map = {
        'Overloaded': '#ffcccc',
        'Underutilized': '#ccffcc', 
        'Normal': '#ffffcc'
    }
    
    # Reset index untuk memulai dari 1
    display_df = df_selected_date.copy().reset_index(drop=True)
    display_df.index = display_df.index + 1
    
    # Formatting dataframe
    styled_df = display_df.style.apply(
        lambda x: [f"background-color: {color_map.get(x['Kriteria Gangguan'], '')}" for _ in x],
        axis=1
    )
    st.dataframe(styled_df, use_container_width=True)

    # Optimisasi Otomatis
    st.subheader("🚀 Optimisasi Penempatan")
    
    if st.button("⚡ Jalankan Optimisasi untuk Tanggal Ini"):
        with st.spinner('Mengoptimasi penempatan mahasiswa...'):
            df_optimized, df_peserta_opt, relokasi_mahasiswa = optimize_schedule(df, df_peserta, selected_date)
            
            # Simpan hasil optimasi ke session state
            st.session_state['df_wahana_optimized'] = df_optimized
            st.session_state['df_peserta_opt'] = df_peserta_opt
            st.session_state['relokasi_mahasiswa'] = relokasi_mahasiswa
            st.session_state['is_optimized'] = True
            
            # Filter data untuk tanggal yang dipilih
            df_opt_selected_date = df_optimized[df_optimized['Tanggal'] == selected_date]
            
            # Reset index untuk tampilan tabel (dimulai dari 1)
            display_before = df_selected_date.copy().reset_index(drop=True)
            display_before.index = display_before.index + 1
            
            display_after = df_opt_selected_date.copy().reset_index(drop=True)
            display_after.index = display_after.index + 1
            
            # Tampilkan perbandingan
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"### Sebelum Optimisasi")
                st.dataframe(
                    display_before.style.apply(lambda x: [f"background-color: {color_map.get(x['Kriteria Gangguan'], '')}" for _ in x], axis=1),
                    height=400
                )
            
            with col2:
                st.markdown(f"### Setelah Optimisasi")
                styled_opt = display_after.style.apply(
                    lambda x: [f"background-color: {color_map.get(x['Kriteria Gangguan'], '')}" for _ in x], 
                    axis=1
                )
                st.dataframe(styled_opt, height=400)
            
            st.success("✅ Optimisasi berhasil diterapkan!")
            
            # Tampilkan informasi relokasi untuk tanggal yang dipilih
            relokasi_for_date = [r for r in relokasi_mahasiswa if r['Tanggal'] == selected_date]
            if relokasi_for_date:
                st.subheader(f"🔄 Rincian Relokasi Mahasiswa")
                df_relokasi = pd.DataFrame(relokasi_for_date)
                # Format tanggal untuk tampilan yang lebih baik
                if 'Tanggal' in df_relokasi.columns:
                    df_relokasi['Tanggal'] = df_relokasi['Tanggal'].apply(lambda x: x.strftime('%d %B %Y') if isinstance(x, datetime) else x)
                
                # Reset index dimulai dari 1
                df_relokasi = df_relokasi.reset_index(drop=True)
                df_relokasi.index = df_relokasi.index + 1
                
                st.dataframe(df_relokasi, use_container_width=True)
            else:
                st.info(f"Tidak ada relokasi mahasiswa yang diperlukan untuk tanggal {selected_date.strftime('%d %B %Y')}.")

    # Visualisasi Distribusi Status
    st.subheader(f"📊 Distribusi Status RS")
    
    if 'is_optimized' in st.session_state and st.session_state['is_optimized']:
        # Tampilkan tab untuk memilih visualisasi sebelum atau setelah optimasi
        tab1, tab2 = st.tabs(["Sebelum Optimisasi", "Setelah Optimisasi"])
        
        with tab1:
            # Visualisasi status sebelum optimasi
            status_count = df_selected_date['Kriteria Gangguan'].value_counts().reset_index()
            status_count.columns = ['Status', 'Count']
            
            chart = alt.Chart(status_count).mark_arc().encode(
                theta='Count',
                color=alt.Color('Status', scale=alt.Scale(
                    domain=['Overloaded', 'Underutilized', 'Normal'],
                    range=['#ff0000', '#00ff00', '#ffff00'])
                ),
                tooltip=['Status', 'Count']
            ).properties(height=300, title=f"Distribusi Status RS Sebelum Optimisasi")
            
            st.altair_chart(chart, use_container_width=True)
            
            # Tampilkan metrik ringkasan
            col1, col2, col3 = st.columns(3)
            with col1:
                overload_count = len(df_selected_date[df_selected_date['Kriteria Gangguan'] == 'Overloaded'])
                st.metric("Overloaded", f"{overload_count} RS")
            with col2:
                normal_count = len(df_selected_date[df_selected_date['Kriteria Gangguan'] == 'Normal'])
                st.metric("Normal", f"{normal_count} RS")
            with col3:
                under_count = len(df_selected_date[df_selected_date['Kriteria Gangguan'] == 'Underutilized'])
                st.metric("Underutilized", f"{under_count} RS")
        
        with tab2:
            # Visualisasi status setelah optimasi
            df_optimized = st.session_state['df_wahana_optimized']
            df_opt_selected_date = df_optimized[df_optimized['Tanggal'] == selected_date]
            status_count_opt = df_opt_selected_date['Kriteria Gangguan'].value_counts().reset_index()
            status_count_opt.columns = ['Status', 'Count']
            
            chart_opt = alt.Chart(status_count_opt).mark_arc().encode(
                theta='Count',
                color=alt.Color('Status', scale=alt.Scale(
                    domain=['Overloaded', 'Underutilized', 'Normal'],
                    range=['#ff0000', '#00ff00', '#ffff00'])
                ),
                tooltip=['Status', 'Count']
            ).properties(height=300, title=f"Distribusi Status RS Setelah Optimisasi")
            
            st.altair_chart(chart_opt, use_container_width=True)
            
            # Tampilkan metrik ringkasan setelah optimasi
            col1, col2, col3 = st.columns(3)
            with col1:
                overload_count = len(df_opt_selected_date[df_opt_selected_date['Kriteria Gangguan'] == 'Overloaded'])
                prev_overload = len(df_selected_date[df_selected_date['Kriteria Gangguan'] == 'Overloaded'])
                delta = overload_count - prev_overload
                st.metric("Overloaded", f"{overload_count} RS", delta=delta, delta_color="inverse")
            with col2:
                normal_count = len(df_opt_selected_date[df_opt_selected_date['Kriteria Gangguan'] == 'Normal'])
                prev_normal = len(df_selected_date[df_selected_date['Kriteria Gangguan'] == 'Normal'])
                delta = normal_count - prev_normal
                st.metric("Normal", f"{normal_count} RS", delta=delta)
            with col3:
                under_count = len(df_opt_selected_date[df_opt_selected_date['Kriteria Gangguan'] == 'Underutilized'])
                prev_under = len(df_selected_date[df_selected_date['Kriteria Gangguan'] == 'Underutilized'])
                delta = under_count - prev_under
                st.metric("Underutilized", f"{under_count} RS", delta=delta, delta_color="inverse")
    else:
        # Visualisasi status sebelum optimasi
        status_count = df_selected_date['Kriteria Gangguan'].value_counts().reset_index()
        status_count.columns = ['Status', 'Count']
        
        chart = alt.Chart(status_count).mark_arc().encode(
            theta='Count',
            color=alt.Color('Status', scale=alt.Scale(
                domain=['Overloaded', 'Underutilized', 'Normal'],
                range=['#ff0000', '#00ff00', '#ffff00'])
            ),
            tooltip=['Status', 'Count']
        ).properties(height=300)
        
        st.altair_chart(chart, use_container_width=True)

else:
    st.info("📥 Silakan upload file Excel untuk memulai")