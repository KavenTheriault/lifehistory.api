import sqlite3
from datetime import datetime, timedelta
import time

def string_to_date(str_date):
	return datetime.strptime(str_date[:10], '%Y-%m-%d')

def string_to_time(str_time):
	return time.mktime(time.strptime(str_time[11:19], "%H:%M:%S"))

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
							VALUES({0}, date('now'), 'Nourriture', 1, 1) """.format(destination_user_id)
print(food_category_query)
cursorV2.execute(food_category_query)

cursorV2.execute("SELECT id FROM activity_types WHERE name = 'Nourriture'")
food_category_id = cursorV2.fetchone()[0]

#Create food activities
for row in cursorV1.execute("""	SELECT LunchDescription AS Name FROM LH_Eatings WHERE LunchDescription <> ''
								UNION
								SELECT DinnerDescription AS Name FROM LH_Eatings WHERE DinnerDescription <> ''
								UNION
								SELECT SupperDescription AS Name FROM LH_Eatings WHERE SupperDescription <> '' """):
	food_activity_query = "INSERT INTO activities(user_id, created_date, name, activity_type_id) VALUES({0}, date('now'), ?, {1})".format(destination_user_id, food_category_id)
	print(food_activity_query)
	cursorV2.execute(food_activity_query, (row[0],))

#Create days
cursorV1.execute("SELECT MIN(Date) AS Date FROM LH_Eatings UNION SELECT MAX(Date) AS Date FROM LH_Eatings")
min_date = string_to_date(cursorV1.fetchone()[0])
max_date = string_to_date(cursorV1.fetchone()[0])

for single_date in daterange(min_date, max_date):
	day_query = "INSERT INTO days(user_id, created_date, date) VALUES({0}, date('now'), ?)".format(destination_user_id)
	cursorV2.execute(day_query, (single_date,))

for row in cursorV1.execute("""	SELECT LunchDescription AS Name, LunchHour AS Time, Date, LunchQuantity AS Quantity FROM LH_Eatings WHERE LunchDescription <> ''
								UNION
								SELECT DinnerDescription AS Name, DinnerHour AS Time, Date, DinnerQuantity AS Quantity FROM LH_Eatings WHERE DinnerDescription <> ''
								UNION
								SELECT SupperDescription AS Name, SupperHour AS Time, Date, SupperQuantity AS Quantity FROM LH_Eatings WHERE SupperDescription <> '' """):
	cursorV2.execute("SELECT id FROM activities WHERE name = ?", (row[0],))
	activity_id = cursorV2.fetchone()[0]
	
	cursorV2.execute("SELECT id FROM days WHERE date = ?", (string_to_date(row[2]),))
	day_id = cursorV2.fetchone()[0]

	life_entry_query = "INSERT INTO life_entries(user_id, created_date, day_id, start_time) VALUES({0}, date('now'), ?, ?)".format(destination_user_id)
	cursorV2.execute(life_entry_query, (day_id, string_to_time(row[1])))
	
	life_entry_id = cursorV2.lastrowid
	
	life_entry_activity_query = "INSERT INTO life_entry_activities(user_id, created_date, life_entry_id, activity_id, Quantity) VALUES({0}, date('now'), ?, ?, ?)".format(destination_user_id)
	cursorV2.execute(life_entry_activity_query, (life_entry_id, activity_id, row[3]))


#connV1.commit()
connV1.close()
print("Connection to 'LFDB.db' (V1) is now closed and commited.")

#connV2.commit()
connV2.close()
print("Connection to 'db.sqlite' (V2) is now closed and commited.")