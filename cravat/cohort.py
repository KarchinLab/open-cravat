import sqlite3

def write_cohorts(cohorts_path, conn):
    cursor = conn.cursor()
    cursor.execute('create table if not exists cohorts (sample text, cohort text);')
    cohort_pairs = []
    with open(cohorts_path) as f:
        for l in f:
            sample, cohorts = l.strip().split()
            cohorts = cohorts.split(',')
            for cohort in cohorts:
                cohort_pairs.append((sample, cohort))
    cursor.executemany('insert into cohorts (sample, cohort) values (?,?)', cohort_pairs)
    cursor.execute('create index if not exists cohorts_cohort on cohorts (cohort);')
    cursor.execute('create index if not exists cohorts_sample on cohorts (sample);')
    cursor.close()
    conn.commit()
