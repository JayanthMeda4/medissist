import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

def db_connect():
    try:
        db = pymysql.connect(host=os.getenv("DB_HOSTNAME"), user=os.getenv("DB_USER"),
                             password=os.getenv("DB_PASSWORD"),
                             database=os.getenv("DB_NAME"))
        return db
    except Exception as e:
        print('the error in db_conn------>', e)
        raise e


def db_insert(tablename, column_dict, db, close_conn=True):
    try:
        cursor = db.cursor()
        col_keys = tuple(column_dict.keys())
        col_values = tuple(column_dict.values())
        query_placeholders = ', '.join(['%s'] * len(col_values))
        query_columns = ', '.join(col_keys)
        insert_query = "INSERT INTO " + tablename + " (%s) VALUES (%s) " % (query_columns, query_placeholders)
        cursor.execute(insert_query, col_values)
        num_affected_rows = cursor.rowcount
        db.commit()
        cursor.close()
        return num_affected_rows
    except Exception as e:
        print('The error in DB_insert is ', e)
        raise e
    finally:
        if close_conn and 'db' in locals() and db.open:
            db.close()


def db_update(tablename, column_dict, where: dict, db, close_conn=True):
    try:
        cursor = db.cursor()
        where_key_list, where_value_list = [], []
        for where_row in list(where.items()):
            where_key_list.append(where_row[0])
            where_value_list.append(where_row[1])

        update_string = " "
        update_values = []
        for data in column_dict.items():
            update_string += data[0] + '=%s,'
            update_values.append(data[1])
        update_values.extend(where_value_list)
        where_clause = " AND ".join([f"{key}=%s" for key in where_key_list])
        sql_query = "UPDATE " + tablename + " SET" + update_string[:-1] + f" WHERE {where_clause}"
        values = update_values
        cursor.execute(sql_query, values)
        num_affected_rows = cursor.rowcount
        db.commit()
        cursor.close()
        return num_affected_rows
    except Exception as e:
        print('The error in DB_update is ', e)
        raise e
    finally:
        if close_conn and 'db' in locals() and db.open:
            db.close()


def db_fetch(tablename, fetch_list_ids, where: dict, db, output_as_dict=None, close_conn=True):
    try:
        cursor = db.cursor()
        # where_key, where_value = list(where.items())[0]
        filtered_data = " "
        where_string = ' '
        where_values = []
        if isinstance(fetch_list_ids, str):
            filtered_data = '*,'
        elif isinstance(fetch_list_ids, list):
            for data in fetch_list_ids:
                filtered_data += data + ','
        for where_data in where.items():
            if where_data[1] == None:
                where_string += where_data[0] + ' is %s and '
                where_values.append(where_data[1])
            elif where_data[1] == str(not None):
                where_string += where_data[0] + ' is not %s and '
                where_values.append(None)
            else:
                where_string += where_data[0] + '=%s and '
                where_values.append(where_data[1])
        sql_query = "select " + filtered_data[:-1] + ' from ' + tablename + " WHERE " + where_string[:-5]
        # print('the sql_query is-------------->',sql_query)
        values = where_values
        cursor.execute(sql_query, values)
        if output_as_dict:
            row_headers = [x[0] for x in cursor.description]
            users = cursor.fetchall()
            data = []
            for result in users:
                data.append(dict(zip(row_headers, result)))
        else:
            data = cursor.fetchall()
        cursor.close()
        return data

    except Exception as e:
        print('The error in DB_fetch is ', e)
        raise e
    finally:
        if close_conn and 'db' in locals() and db.open:
            db.close()