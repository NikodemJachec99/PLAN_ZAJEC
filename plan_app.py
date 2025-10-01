import streamlit as st
import pandas as pd
from datetime import datetime
import io
from xhtml2pdf import pisa # NOWOŚĆ: import do generowania PDF

# --- Funkcja do generowania HTML (bez zmian) ---
def generate_html_schedule(df):
    """Generuje nowoczesny i estetyczny plan zajęć w formacie HTML."""
    # Przetwarzanie danych (logika pozostaje bez zmian)
    df.columns = [
        'date', 'day_of_week', 'start_time', 'end_time', 'subject', 'type',
        'degree', 'first_name', 'last_name', 'room', 'field_year', 'group',
        'info_combined', 'additional_info'
    ] + [f'unnamed_{i}' for i in range(len(df.columns) - 14)]

    df_cleaned = df[['date', 'day_of_week', 'start_time', 'end_time', 'subject', 'type', 'degree', 'first_name', 'last_name', 'room', 'group']].copy()
    df_cleaned.dropna(subset=['date'], inplace=True)
    df_cleaned['date'] = pd.to_datetime(df_cleaned['date'], errors='coerce')
    df_cleaned.dropna(subset=['date'], inplace=True)
    
    df_cleaned['instructor'] = (df_cleaned['degree'].fillna('') + ' ' + df_cleaned['first_name'].fillna('') + ' ' + df_cleaned['last_name'].fillna('')).str.strip()
    df_cleaned['start_time'] = df_cleaned['start_time'].apply(lambda x: x.strftime('%H:%M') if isinstance(x, (datetime, pd.Timestamp)) else str(x)).str.slice(0, 5)
    df_cleaned['end_time'] = df_cleaned['end_time'].apply(lambda x: x.strftime('%H:%M') if isinstance(x, (datetime, pd.Timestamp)) else str(x)).str.slice(0, 5)
    df_cleaned['group'] = df_cleaned['group'].fillna('---').astype(str)
    
    df_cleaned['iso_year'] = df_cleaned['date'].dt.isocalendar().year
    df_cleaned['iso_week'] = df_cleaned['date'].dt.isocalendar().week
    df_cleaned.sort_values(by=['date', 'start_time'], inplace=True)

    # Kod HTML i CSS (bez zmian)
    html = """
    <!DOCTYPE html>
    <html lang="pl">
    <head>
        <meta charset="UTF-8">
        <title>Plan Zajęć</title>
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
        <style>
            :root {
                --font-family-sans: 'Inter', sans-serif;
                --background-color: #f8f9fa;
                --card-background-color: #ffffff;
                --text-color: #212529;
                --header-gradient: linear-gradient(45deg, #1d2a35, #2c3e50);
                --accent-color: #007bff;
                --border-color: #dee2e6;
                --shadow: 0 8px 16px rgba(0,0,0,0.05);
                --border-radius: 12px;
            }
            body { 
                font-family: var(--font-family-sans); 
                background-color: var(--card-background-color); 
                color: var(--text-color); 
                margin: 0; 
                padding: 2rem;
            }
            .container { max-width: 1400px; margin: auto; }
            h1 { font-size: 2.5rem; font-weight: 700; text-align: center; margin-bottom: 2.5rem; color: #2c3e50; }
            .week-container { background-color: var(--card-background-color); border-radius: var(--border-radius); box-shadow: var(--shadow); margin-bottom: 2.5rem; overflow: hidden; border: 1px solid var(--border-color); }
            .week-header { background: var(--header-gradient); color: white; padding: 1.5rem 2rem; display: flex; justify-content: space-between; align-items: center; }
            .week-header h2 { margin: 0; font-size: 1.75rem; font-weight: 600; }
            .week-header .date-range { font-size: 1rem; font-weight: 400; opacity: 0.8; }
            .day-container { padding: 1.5rem 2rem; border-bottom: 1px solid var(--border-color); }
            .day-container:last-child { border-bottom: none; }
            h3 { font-size: 1.5rem; font-weight: 600; color: var(--accent-color); margin-top: 0; margin-bottom: 1.5rem; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 1rem; text-align: left; border-bottom: 1px solid var(--border-color); vertical-align: middle; }
            thead th { background-color: #f1f3f5; color: #495057; font-size: 0.875rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
            tr:nth-child(even) td { background-color: #f8f9fa; }
            .badge { display: inline-block; padding: 0.4em 0.8em; font-size: 0.85em; font-weight: 500; line-height: 1; text-align: center; white-space: nowrap; vertical-align: baseline; border-radius: 20px; color: #fff; }
            .badge-type { background-color: #17a2b8; }
            .badge-room { background-color: #dc3545; }
            .badge-group { background-color: #6f42c1; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Oto Twój Plan Zajęć ❤️</h1>
    """ + ''.join([
        f"""
        <div class="week-container">
            <div class="week-header">
                <h2>Tydzień {week_num}</h2>
                <span class="date-range">{week_df['date'].min().strftime('%d.%m.%Y')} - {week_df['date'].max().strftime('%d.%m.%Y')}</span>
            </div>
        """ + ''.join([
            f"""
            <div class='day-container'>
                <h3>{day_df['day_of_week'].iloc[0].capitalize()}, {day.strftime('%d.%m.%Y')}</h3>
                <table>
                    <thead>
                        <tr><th>Godzina</th><th>Przedmiot</th><th>Typ</th><th>Wykładowca</th><th>Sala</th><th>Grupa</th></tr>
                    </thead>
                    <tbody>
            """ + ''.join([
                f"""
                <tr>
                    <td>{row['start_time']} - {row['end_time']}</td>
                    <td>{row['subject']}</td>
                    <td><span class="badge badge-type">{row['type']}</span></td>
                    <td>{row['instructor']}</td>
                    <td><span class="badge badge-room">{row['room']}</span></td>
                    <td><span class="badge badge-group">{row['group']}</span></td>
                </tr>
                """ for _, row in day_df.iterrows()
            ]) + """
                    </tbody>
                </table>
            </div>
            """ for day, day_df in week_df.groupby('date')
        ]) + "</div>" for (year, week_num), week_df in df_cleaned.groupby(['iso_year', 'iso_week'])
    ]) + """
        </div>
    </body>
    </html>
    """
    return html

# --- NOWOŚĆ: Funkcja do konwersji HTML na PDF ---
def convert_html_to_pdf(html_string):
    """Konwertuje string HTML na bajty PDF, gotowe do pobrania."""
    pdf_output = io.BytesIO()
    # Konwersja HTML do PDF
    pisa_status = pisa.CreatePDF(
        io.StringIO(html_string),  # źródło HTML
        dest=pdf_output            # cel (plik w pamięci)
    )
    if pisa_status.err:
        return None
    pdf_output.seek(0)
    return pdf_output

# --- Główna aplikacja Streamlit ---
st.set_page_config(page_title="Plan Zajęć Madzi", page_icon="📅", layout="wide")

st.title('Plan Zajęć Madzi')
st.markdown("Przeciągnij i upuść plik Excel (`.xlsx`) z planem, a ja zamienię go w nowoczesny i interaktywny harmonogram.")

uploaded_file = st.file_uploader(
    "Wybierz plik Excel z planem zajęć", 
    type=['xlsx'],
    help="Upewnij się, że nagłówek tabeli znajduje się w czwartym wierszu pliku."
)

if uploaded_file is not None:
    try:
        df = pd.read_excel(uploaded_file, header=3)
        st.success("Plik wczytany! Plan gotowy do pobrania. ✨")
        
        # Generowanie HTML i PDF
        html_output = generate_html_schedule(df)
        pdf_output = convert_html_to_pdf(html_output) # NOWOŚĆ

        st.subheader("Podgląd wygenerowanego planu")
        st.components.v1.html(html_output, height=720, scrolling=True)

        st.subheader("Pobierz swój plan")
        # --- NOWOŚĆ: Dwa przyciski w kolumnach ---
        col1, col2 = st.columns(2)
        with col1:
            st.download_button(
                label="Pobierz jako HTML",
                data=html_output,
                file_name=f"plan_zajec_{datetime.now().strftime('%Y-%m-%d')}.html",
                mime="text/html",
                use_container_width=True
            )
        with col2:
            if pdf_output: # Sprawdzamy, czy PDF został poprawnie utworzony
                st.download_button(
                    label="Pobierz jako PDF",
                    data=pdf_output,
                    file_name=f"plan_zajec_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )

    except Exception as e:
        st.error(f"Wystąpił błąd podczas przetwarzania pliku: {e}")
        st.warning("Sprawdź, czy plik `.xlsx` ma poprawną strukturę (nagłówek w 4. wierszu).")
else:
    st.info("Oczekuję na wgranie pliku...")

st.markdown("---")
st.write("Made with ❤️")
