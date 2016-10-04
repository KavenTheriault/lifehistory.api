import sqlite3

connV1 = sqlite3.connect('LFDB.db')
print("Connection to 'LFDB.db' (V1) done.")

connV2 = sqlite3.connect('db.sqlite')
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
print("The food_category_id is {0}".format(food_category_id))

for row in cursorV1.execute("""	SELECT LunchDescription AS Name FROM LH_Eatings WHERE LunchDescription <> ''
								UNION
								SELECT DinnerDescription AS Name FROM LH_Eatings WHERE DinnerDescription <> ''
								UNION
								SELECT SupperDescription AS Name FROM LH_Eatings WHERE SupperDescription <> '' """):
	food_activity_query = "INSERT INTO activities(user_id, created_date, name, activity_type_id) VALUES({0}, date('now'), '{2}', {1})".format(destination_user_id, food_category_id, row[0])
	print(food_activity_query)

for row in cursorV2.execute('SELECT * FROM users'):
    print(row)

#connV1.commit()
connV1.close()

#connV2.commit()
connV2.close()