import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# --- Konfiguracja strony ---
st.set_page_config(page_title="Interaktywny Plan Zajęć", page_icon="📅", layout="centered")

# --- Wczytywanie i przetwarzanie danych ---
@st.cache_data(ttl=600) # Odśwież dane co 10 minut
def load_data(file_path):
    """Wczytuje i przetwarza dane z pliku Excel."""
    df = pd.read_excel(file_path, header=3)
    
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
    df_cleaned['group'] = df_cleaned['group'].fillna('---').astype(str)
    
    df_cleaned['start_time_obj'] = pd.to_datetime(df_cleaned['start_time'], format='%H:%M:%S', errors='coerce').dt.time
    df_cleaned['start_time'] = df_cleaned['start_time_obj'].apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')
    df_cleaned['end_time'] = pd.to_datetime(df_cleaned['end_time'], format='%H:%M:%S', errors='coerce').dt.time.apply(lambda x: x.strftime('%H:%M') if pd.notnull(x) else 'Błąd')

    df_cleaned.sort_values(by=['date', 'start_time_obj'], inplace=True)
    return df_cleaned

# --- Style CSS dla nowego, responsywnego wyglądu ---
st.markdown("""
<style>
    /* Ukrycie domyślnego nagłówka Streamlit */
    .stApp > header {
        background-color: transparent;
    }
    /* Główny kontener */
    .main .block-container {
        padding: 1rem 1rem 5rem 1rem;
    }
    /* Tytuł aplikacji */
    h1 {
        text-align: center;
        color: #1a202c;
        margin-bottom: 0;
    }
    /* Podtytuł */
    .subtitle {
        text-align: center;
        color: #718096;
        margin-bottom: 2rem;
    }
    /* Kontener nawigacji */
    .nav-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        background-color: #ffffff;
        padding: 0.5rem 1rem;
        border-radius: 0.75rem;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.03);
        margin-bottom: 2rem;
    }
    .nav-container h2 {
        margin: 0;
        font-size: 1.25rem;
        color: #2d3748;
        font-weight: 600;
    }
    /* Karta dnia */
    .day-container {
        margin-bottom: 2rem;
    }
    .day-header {
        display: flex;
        align-items: baseline;
        gap: 0.75rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .day-header.today h3, .day-header.today .date-span {
        color: #2563eb;
    }
    .day-header h3 {
        margin: 0;
        font-size: 1.5rem;
        color: #2d3748;
    }
    .day-header .date-span {
        color: #718096;
        font-size: 1rem;
    }
    /* Karta zajęć */
    .class-card {
        display: flex;
        gap: 1rem;
        padding: 1rem 0;
        border-bottom: 1px solid #f1f3f5;
    }
    .class-time {
        font-weight: 600;
        color: #1a202c;
        font-size: 0.9rem;
        width: 100px; /* Stała szerokość dla wyrównania */
    }
    .class-content {
        flex-grow: 1;
    }
    .class-subject {
        font-weight: 600;
        font-size: 1.05em;
        margin-bottom: 0.25rem;
        color: #2d3748;
    }
    .class-details {
        font-size: 0.9em;
        color: #718096;
    }
    /* Linia czasu */
    .timeline-container {
        position: relative;
    }
    .timeline {
        position: absolute;
        left: -1rem; /* Wyjście poza padding karty */
        right: -1rem;
        height: 2px;
        background-color: #ef4444;
        z-index: 10;
    }
    .timeline::before {
        content: '';
        position: absolute;
        left: 1rem; /* Wyrównanie z treścią */
        top: -4px;
        width: 10px;
        height: 10px;
        background-color: #ef4444;
        border-radius: 50%;
    }
</style>
""", unsafe_allow_html=True)

# --- Logika aplikacji ---
try:
    df = load_data("plan_zajec.xlsx")

    st.title("Plan Zajęć")
    st.markdown("<p class='subtitle'>Interaktywny harmonogram na cały semestr</p>", unsafe_allow_html=True)
    
    if 'current_week_start' not in st.session_state:
        today = datetime.now().date()
        st.session_state.current_week_start = today - timedelta(days=today.weekday())

    # --- Nawigacja ---
    week_start = st.session_state.current_week_start
    week_end = week_start + timedelta(days=6)
    
    nav_cols = st.columns([1, 4, 1])
    with nav_cols[0]:
        if st.button("⬅️", use_container_width=True):
            st.session_state.current_week_start -= timedelta(days=7)
            st.rerun() # Natychmiastowe odświeżenie
    with nav_cols[2]:
        if st.button("➡️", use_container_width=True):
            st.session_state.current_week_start += timedelta(days=7)
            st.rerun()
    with nav_cols[1]:
        st.markdown(f"<div class='nav-container'><h2>{week_start.strftime('%d.%m')} - {week_end.strftime('%d.%m.%Y')}</h2></div>", unsafe_allow_html=True)

    # --- Wyświetlanie tygodnia ---
    today_date = datetime.now().date()
    current_time_obj = datetime.now().time()
    
    days_of_week_pl = ["Poniedziałek", "Wtorek", "Środa", "Czwartek", "Piątek", "Sobota", "Niedziela"]

    for i in range(7):
        current_day = week_start + timedelta(days=i)
        day_events = df[df['date'].dt.date == current_day]
        
        is_today_class = "today" if current_day == today_date else ""
        
        st.markdown(f'<div class="day-container">', unsafe_allow_html=True)
        st.markdown(f"""
            <div class="day-header {is_today_class}">
                <h3>{days_of_week_pl[i]}</h3>
                <span class="date-span">{current_day.strftime('%d.%m')}</span>
            </div>
        """, unsafe_allow_html=True)
        
        container = st.container()
        
        if not day_events.empty:
            container.markdown('<div class="timeline-container">', unsafe_allow_html=True) # Kontener dla linii czasu
            
            # Linia czasu
            if current_day == today_date:
                day_start_hour, day_end_hour = 8, 20
                total_seconds = (day_end_hour - day_start_hour) * 3600
                current_seconds = (current_time_obj.hour - day_start_hour) * 3600 + current_time_obj.minute * 60 + current_time_obj.second
                if 0 <= current_seconds <= total_seconds:
                    top_percentage = (current_seconds / total_seconds) * 100
                    # Używamy pustego kontenera jako "płótna" dla linii
                    placeholder = container.empty()
                    placeholder.markdown(f'<div class="timeline" style="top: {top_percentage}%;"></div>', unsafe_allow_html=True)

            # Zajęcia
            for _, event in day_events.iterrows():
                container.markdown(f"""
                <div class="class-card">
                    <div class="class-time">{event['start_time']}</div>
                    <div class="class-content">
                        <div class="class-subject">{event['subject']}</div>
                        <div class="class-details">
                            <span>{event['instructor']}</span> &bull; 
                            <span>Sala: {event['room']}</span> &bull; 
                            <span>Gr: {event['group']}</span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            container.markdown('</div>', unsafe_allow_html=True)
        else:
            container.markdown("<p style='color: #adb5bd; padding: 2rem 0;'>Brak zajęć</p>", unsafe_allow_html=True)

        st.markdown('</div>', unsafe_allow_html=True)
        
except FileNotFoundError:
    st.error("Nie znaleziono pliku `plan_zajec.xlsx`. Upewnij się, że plik znajduje się w repozytorium na GitHubie.")
except Exception as e:
    st.error(f"Wystąpił nieoczekiwany błąd: {e}")
