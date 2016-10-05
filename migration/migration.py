import sqlite3
from datetime import datetime, timedelta
import time

def string_to_date(str_date):
	return datetime.strptime(str_date[:10], '%Y-%m-%d')

def date_to_string(my_date):
	return my_date.strftime('%Y-%m-%d %H:%M:%S.%f') #2016-10-04 20:20:34.230000

def get_correct_time_str(str_time):
	return str_time[11:19]

def daterange(start_date, end_date):
	for n in range(int ((end_date - start_date + timedelta(1)).days)):
		yield start_date + timedelta(n)

connV1 = sqlite3.connect('LFDB.db')
connV1.set_trace_callback(print)
print("Connection to 'LFDB.db' (V1) done.")

connV2 = sqlite3.connect('db.sqlite')
connV2.set_trace_callback(print)
print("Connection to 'db.sqlite' (V2) done.")

cursorV1 = connV1.cursor()
cursorV2 = connV2.cursor()

destination_user_id = 1

#Default Data
food_category_query = """	INSERT INTO activity_types(user_id, created_date, name, show_quantity, show_rating)
							VALUES(?, ?, 'Nourriture', 1, 1) """.format(destination_user_id)
print(food_category_query)
cursorV2.execute(food_category_query, (destination_user_id, datetime.now()))

cursorV2.execute("SELECT id FROM activity_types WHERE name = 'Nourriture'")
food_category_id = cursorV2.fetchone()[0]

#Create food activities
for row in cursorV1.execute("""	SELECT LunchDescription AS Name FROM LH_Eatings WHERE LunchDescription <> ''
								UNION
								SELECT DinnerDescription AS Name FROM LH_Eatings WHERE DinnerDescription <> ''
								UNION
								SELECT SupperDescription AS Name FROM LH_Eatings WHERE SupperDescription <> '' """):
	food_activity_query = "INSERT INTO activities(user_id, created_date, name, activity_type_id) VALUES(?, ?, ?, ?)"
	print(food_activity_query)
	cursorV2.execute(food_activity_query, (destination_user_id, datetime.now(), row[0], food_category_id))

#Create days
cursorV1.execute("SELECT MIN(Date) AS Date FROM LH_Eatings UNION SELECT MAX(Date) AS Date FROM LH_Eatings")
min_date = string_to_date(cursorV1.fetchone()[0])
max_date = string_to_date(cursorV1.fetchone()[0])

for single_date in daterange(min_date, max_date):
	day_query = "INSERT INTO days(user_id, created_date, date) VALUES(?, ?, ?)"
	cursorV2.execute(day_query, (destination_user_id, datetime.now(), date_to_string(single_date)))

#Create food life entries
for row in cursorV1.execute("""	SELECT LunchDescription AS Name, LunchHour AS Time, Date, LunchQuantity AS Quantity FROM LH_Eatings WHERE LunchDescription <> ''
								UNION
								SELECT DinnerDescription AS Name, DinnerHour AS Time, Date, DinnerQuantity AS Quantity FROM LH_Eatings WHERE DinnerDescription <> ''
								UNION
								SELECT SupperDescription AS Name, SupperHour AS Time, Date, SupperQuantity AS Quantity FROM LH_Eatings WHERE SupperDescription <> '' """):
	cursorV2.execute("SELECT id FROM activities WHERE name = ?", (row[0],))
	activity_id = cursorV2.fetchone()[0]
	
	cursorV2.execute("SELECT id FROM days WHERE date = ?", (date_to_string(string_to_date(row[2])),))
	day_id = cursorV2.fetchone()[0]

	life_entry_query = "INSERT INTO life_entries(user_id, created_date, day_id, start_time) VALUES(?, ?, ?, ?)"
	cursorV2.execute(life_entry_query, (destination_user_id, datetime.now(), day_id, get_correct_time_str(row[1])))

	life_entry_id = cursorV2.lastrowid
	
	life_entry_activity_query = "INSERT INTO life_entry_activities(user_id, created_date, life_entry_id, activity_id, Quantity) VALUES(?, ?, ?, ?, ?)"
	cursorV2.execute(life_entry_activity_query, (destination_user_id, datetime.now(), life_entry_id, activity_id, row[3]))


connV1.commit()
connV1.close()
print("Connection to 'LFDB.db' (V1) is now closed and commited.")

connV2.commit()
connV2.close()
print("Connection to 'db.sqlite' (V2) is now closed and commited.")