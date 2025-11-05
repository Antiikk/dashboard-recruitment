import streamlit as st
import pandas as pd
from datetime import datetime, timedelta

# === НАСТРОЙКА: Вставьте сюда ID вашей Google Таблицы ===
GOOGLE_SHEET_ID = "1XSzNGtQQJBvRTfH0YXlM8j7Z3RS9QalJWIezipdwSzs"
GOOGLE_SHEET_NAME = "Общая_Вакансии"  # Имя листа, откуда брать данные

# Формируем URL для экспорта в CSV
url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/gviz/tq?tqx=out:csv&sheet={GOOGLE_SHEET_NAME}"

@st.cache_data(ttl=300)  # кэш на 5 минут
def load_data():
    try:
        # Пробуем загрузить с UTF-8
        df = pd.read_csv(url, encoding='utf-8', on_bad_lines='skip')
        # Если не получилось — пробуем latin1
        if df.empty:
            df = pd.read_csv(url, encoding='latin1', on_bad_lines='skip')
        
        # Очистка колонок
        df.columns = df.columns.str.strip()
        # Приведение даты к формату
        if 'Дата заявки' in df.columns:
            df['Дата заявки'] = pd.to_datetime(df['Дата заявки'], dayfirst=True, errors='coerce')
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        return pd.DataFrame()

# Загрузка данных
df = load_data()

if df.empty:
    st.warning("Нет данных. Проверьте настройки Google Таблицы.")
else:
    st.title("📊 Аналитика вакансий по ТЗ")

    # --- Определяем периоды ---
    today = pd.Timestamp.today().normalize()
    current_week = today.isocalendar().week
    current_month = today.month
    current_year = today.year

    # Добавляем колонки для фильтрации
    df['Неделя'] = df['Дата заявки'].dt.isocalendar().week
    df['Месяц'] = df['Дата заявки'].dt.month
    df['Год'] = df['Дата заявки'].dt.year

    # Фильтр только по нужным рекрутерам
    target_recruiters = ['Скороходов А.', 'Просянникова П.', 'Березняк О.']
    df_team = df[df['Рекрутер'].isin(target_recruiters)].copy()

    # -----------------------------
    # ЛЕВАЯ ЧАСТЬ: Основная сводка
    # -----------------------------
    st.header("Основная сводка")

    def get_counts(data_frame, period_filter=None):
        if period_filter == 'today':
            data_frame = data_frame[data_frame['Дата заявки'].dt.normalize() == today]
        elif period_filter == 'week':
            data_frame = data_frame[
                (data_frame['Неделя'] == current_week) &
                (data_frame['Год'] == current_year)
            ]
        elif period_filter == 'month':
            data_frame = data_frame[
                (data_frame['Месяц'] == current_month) &
                (data_frame['Год'] == current_year)
            ]
        total = len(data_frame)
        in_work = len(data_frame[data_frame['Статус'] == 'В работе'])
        pending = len(data_frame[data_frame['Статус'] == 'В ожидании'])
        paused = len(data_frame[data_frame['Статус'] == 'Приостановлена'])
        return total, in_work, pending, paused

    periods = {
        'Сейчас (сегодня)': 'today',
        'На этой неделе': 'week',
        'В этом месяце': 'month'
    }

    # Таблица для основной сводки
    summary_data = []
    for label, key in periods.items():
        total, in_work, pending, paused = get_counts(df, key)
        summary_data.append({
            'Период': label,
            'Всего вакансий': total,
            'В работе': in_work,
            'В ожидании': pending,
            'Приостановлены': paused
        })

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True)

    # -----------------------------
    # ПРАВАЯ ЧАСТЬ: Аналитика по рекрутерам
    # -----------------------------
    st.header("Аналитика по рекрутерам (только команда)")

    def get_recruiter_stats(recruiter_df, period_filter=None):
        if period_filter == 'today':
            recruiter_df = recruiter_df[recruiter_df['Дата заявки'].dt.normalize() == today]
        elif period_filter == 'week':
            recruiter_df = recruiter_df[
                (recruiter_df['Неделя'] == current_week) &
                (recruiter_df['Год'] == current_year)
            ]
        elif period_filter == 'month':
            recruiter_df = recruiter_df[
                (recruiter_df['Месяц'] == current_month) &
                (recruiter_df['Год'] == current_year)
            ]
        return {
            'Всего': len(recruiter_df),
            'В работе': len(recruiter_df[recruiter_df['Статус'] == 'В работе']),
            'В ожидании': len(recruiter_df[recruiter_df['Статус'] == 'В ожидании']),
            'Приостановлены': len(recruiter_df[recruiter_df['Статус'] == 'Приостановлена'])
        }

    recruiter_summary = []
    for recruiter in target_recruiters:
        r_df = df_team[df_team['Рекрутер'] == recruiter]
        stats_now = get_recruiter_stats(r_df, 'today')
        stats_week = get_recruiter_stats(r_df, 'week')
        stats_month = get_recruiter_stats(r_df, 'month')
        recruiter_summary.append({
            'Рекрутер': recruiter,
            'Всего сейчас': stats_now['Всего'],
            'Всего за неделю': stats_week['Всего'],
            'Всего за месяц': stats_month['Всего'],
            'В работе': stats_now['В работе'],
            'В ожидании': stats_now['В ожидании'],
            'Приостановлены': stats_now['Приостановлены'],
        })

    recruiter_df = pd.DataFrame(recruiter_summary)
    st.dataframe(recruiter_df, use_container_width=True)

    # -----------------------------
    # Дополнительно: средний срок в работе (если есть "Дата закрытия / холда")
    # -----------------------------
    if 'Дата закрытия / холда' in df.columns:
        df_active = df[df['Статус'] == 'В работе'].copy()
        if not df_active.empty:
            df_active['Срок дней'] = (today - df_active['Дата заявки']).dt.days
            avg_days = df_active['Срок дней'].mean()
            st.metric("Средний срок вакансии «в работе» (дни)", f"{avg_days:.1f}")
