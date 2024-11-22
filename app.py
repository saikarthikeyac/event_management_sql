# app.py
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime
import requests

app = Flask(__name__)
CORS(app)
bcrypt = Bcrypt(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'port': '3306',
    'password': 'sai523223',
    'database': 'event5'
}

app.secret_key = 'a3d9e5f4b2c1a6e8f7d3b0c9a1f4e7d8'

# SQL Statements for database setup
SETUP_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(50) UNIQUE NOT NULL,
        email VARCHAR(100) UNIQUE NOT NULL,
        password VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        title VARCHAR(100) NOT NULL,
        description TEXT NOT NULL,
        location VARCHAR(255) NOT NULL,
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        user_id INT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS attendees (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_id INT NOT NULL,
        email VARCHAR(100) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS vendors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_id INT NOT NULL,
        name VARCHAR(100) NOT NULL,
        service VARCHAR(255) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sponsors (
        id INT AUTO_INCREMENT PRIMARY KEY,
        event_id INT NOT NULL,
        name VARCHAR(100) NOT NULL,
        level VARCHAR(50) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """
    """
    CREATE TABLE IF NOT EXISTS event_items (
        item_id INT AUTO_INCREMENT,
        event_id INT,
        item_name VARCHAR(100) NOT NULL,
        quantity INT DEFAULT 1,
        PRIMARY KEY (item_id, event_id),
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
    )
    """
]

def setup_database():
    """Initialize database tables if they don't exist."""
    connection = get_db_connection()
    if connection:
        cursor = connection.cursor()
        try:
            for statement in SETUP_STATEMENTS:
                cursor.execute(statement)
            connection.commit()
            logger.info("Database setup completed successfully")
        except Error as e:
            logger.error(f"Database setup error: {e}")
        finally:
            cursor.close()
            connection.close()

def get_db_connection():
    """Establish and return a MySQL database connection."""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        return connection
    except Error as e:
        logger.error(f"Database connection error: {e}")
        return None

# Existing register and login routes remain the same
@app.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        required_fields = ['username', 'email', 'password']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400
            
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
        
        cursor = connection.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                (data['username'], data['email'], hashed_password)
            )
            connection.commit()
            return jsonify({"message": "User registered successfully!"}), 201
        except Error as e:
            if e.errno == 1062:  # Duplicate entry error
                return jsonify({"message": "Username or email already exists"}), 409
            return jsonify({"message": str(e)}), 400
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({"message": "Internal server error"}), 500


@app.route('/events/attendee/<string:attendee_email>', methods=['GET'])
def get_events_for_attendee(attendee_email):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                SELECT DISTINCT e.id, e.title, e.description, e.location, 
                       e.start_time, e.end_time, e.created_at, e.user_id
                FROM events e 
                JOIN attendees a ON e.id = a.event_id 
                WHERE a.email = %s
            """
            cursor.execute(query, (attendee_email,))
            events = cursor.fetchall()

            for event in events:
                event_id = event['id']

                # Get attendees
                cursor.execute("SELECT email FROM attendees WHERE event_id = %s", (event_id,))
                event['attendees'] = [row['email'] for row in cursor.fetchall()]

                # Get vendors
                cursor.execute("SELECT name, service FROM vendors WHERE event_id = %s", (event_id,))
                event['vendors'] = [{'name': row['name'], 'service': row['service']} 
                                  for row in cursor.fetchall()]

                # Get sponsors
                cursor.execute(""" 
                    SELECT name, level, contribution 
                    FROM sponsors 
                    WHERE event_id = %s""", (event_id,))
                event['sponsors'] = [{'name': row['name'], 'level': row['level'], 
                                    'contribution': float(row['contribution'])} 
                                   for row in cursor.fetchall()]

                # Get event items
                cursor.execute(""" 
                    SELECT item_name, quantity 
                    FROM event_items
                    WHERE event_id = %s""", (event_id,))
                event['items'] = [{'item_name': row['item_name'], 'quantity': row['quantity']} 
                                for row in cursor.fetchall()]

                # Convert datetime objects to strings
                event['start_time'] = event['start_time'].isoformat()
                event['end_time'] = event['end_time'].isoformat()
                event['created_at'] = event['created_at'].isoformat()

            return jsonify({"events": events}), 200
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error fetching events for attendee: {e}")
        return jsonify({"message": "Internal server error"}), 500
@app.route('/events/<int:event_id>/analytics', methods=['GET'])
def get_event_analytics(event_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            # Get event summary
            cursor.execute("""
                SELECT * FROM event_summary 
                WHERE id = %s
            """, (event_id,))
            summary = cursor.fetchone()

            # Get attendee demographics
            cursor.execute("""
                SELECT 
                    COUNT(DISTINCT a.email) as total_attendees,
                    COUNT(DISTINCT s.id) as total_sponsors,
                    COUNT(DISTINCT v.id) as total_vendors,
                    COALESCE(SUM(s.contribution), 0) as total_sponsorship,
                    COALESCE(SUM(v.amount_to_be_paid), 0) as total_costs,
                    calculate_event_profitability(%s) as projected_profit
                FROM events e
                LEFT JOIN attendees a ON e.id = a.event_id
                LEFT JOIN sponsors s ON e.id = s.event_id
                LEFT JOIN vendors v ON e.id = v.event_id
                WHERE e.id = %s
                GROUP BY e.id
            """, (event_id, event_id))
            analytics = cursor.fetchone()

            return jsonify({
                "summary": summary,
                "analytics": analytics
            }), 200

        finally:
            cursor.close()
            connection.close()

    except Exception as e:
        logger.error(f"Error fetching event analytics: {e}")
        return jsonify({"message": "Internal server error"}), 500
    

@app.route('/events/popular', methods=['GET'])
def get_popular_events():
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM event_popularity ORDER BY popularity_rank LIMIT 10")
            popular_events = cursor.fetchall()
            return jsonify({"popular_events": popular_events}), 200

        finally:
            cursor.close()
            connection.close()

    except Exception as e:
        logger.error(f"Error fetching popular events: {e}")
        return jsonify({"message": "Internal server error"}), 500


@app.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        if not all(k in data for k in ['email', 'password']):
            return jsonify({"message": "Missing email or password"}), 400
            
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            # First get the user's password hash
            cursor.execute("SELECT password FROM users WHERE email = %s", (data['email'],))
            user_record = cursor.fetchone()
            
            if not user_record:
                return jsonify({"message": "Invalid credentials"}), 401
                
            # Check if password matches
            if bcrypt.check_password_hash(user_record['password'], data['password']):
                # If password matches, call the MySQL function to get user_id
                cursor.execute(
                    "SELECT check_login_credentials(%s, %s) as user_id",
                    (data['email'], user_record['password'])
                )
                result = cursor.fetchone()
                user_id = result['user_id']
                
                if user_id > 0:
                    return jsonify({
                        "message": "Login successful",
                        "user_id": user_id
                    }), 200
                    
            return jsonify({"message": "Invalid credentials"}), 401
            
        finally:
            cursor.close()
            connection.close()
            
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({"message": "Internal server error"}), 500

@app.route('/events', methods=['POST'])
def create_event():
    try:
        data = request.get_json()
        required_fields = ['title', 'description', 'location', 'start_time', 'end_time', 'user_id', 'attendees']
        
        # Check if all required fields are present
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields", "missing_fields": [field for field in required_fields if field not in data]}), 400
        
        # Validate field values
        try:
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            user_id = int(data['user_id'])
        except ValueError as e:
            return jsonify({"message": "Invalid field value", "error": str(e)}), 400
        
        # Get a database connection
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500
        
        cursor = connection.cursor()
        try:
            # Convert string dates to datetime objects
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
            
            # Log the request data
            logger.info(f"Received request data: {data}")
            
            # Insert the event
            cursor.execute(
                """INSERT INTO events (title, description, location, start_time, end_time, user_id)
                VALUES (%s, %s, %s, %s, %s, %s)""",
                (data['title'], data['description'], data['location'], start_time, end_time, data['user_id'])
            )
            event_id = cursor.lastrowid
            
            # Log the event ID
            logger.info(f"Event created with ID: {event_id}")
            
            # Insert attendees if provided
            if 'attendees' in data and data['attendees']:
                for email in data['attendees']:
                    cursor.execute(
                        "INSERT INTO attendees (event_id, email) VALUES (%s, %s)",
                        (event_id, email)
                    )
            
            # Insert vendors if provided
            if 'vendors' in data and data['vendors']:
                for vendor in data['vendors']:
                    if 'name' not in vendor or 'service' not in vendor:
                        logger.warning("Missing 'name' or 'service' in vendor data")
                        return jsonify({"message": "Each vendor must have 'name' and 'service'"}), 400
                    cursor.execute(
                        "INSERT INTO vendors (event_id, name, service) VALUES (%s, %s, %s)",
                        (event_id, vendor['name'], vendor['service'])
                    )
            
            # Insert sponsors if provided
            if 'sponsors' in data and data['sponsors']:
                for sponsor in data['sponsors']:
                    if not all(k in sponsor for k in ['name', 'level', 'contribution']):
                        return jsonify({"message": "Sponsors must have name, level and contribution"}), 400
                    cursor.execute(
                        """INSERT INTO sponsors (event_id, name, level, contribution)
                        VALUES (%s, %s, %s, %s)""",
                        (event_id, sponsor['name'], sponsor['level'], sponsor.get('contribution', 0.00))
                    )
            
            # Insert event items if provided
            if 'items' in data and data['items']:
                logger.info(f"Items to be inserted: {data['items']}")
                for item in data['items']:
                    if 'item_name' not in item or 'quantity' not in item:
                        return jsonify({"message": "Each item must have 'item_name' and 'quantity'"}), 400
                    cursor.execute(
                        """INSERT INTO event_items (event_id, item_name, quantity)
                        VALUES (%s, %s, %s)""",
                        (event_id, item['item_name'], item['quantity'])
                    )
                    logger.info(f"Inserted item: {item['item_name']} with quantity: {item['quantity']} for event ID: {event_id}")
            
            connection.commit()
            return jsonify({
                "message": "Event created successfully!",
                "event_id": event_id
            }), 201
        except mysql.connector.Error as err:
            connection.rollback()
            logger.error(f"Database error: {err}")
            return jsonify({"message": f"Database error: {err}"}), 400
        except Exception as e:
            logger.error(f"Event creation error: {e}")
            return jsonify({"message": "Internal server error"}), 500

    except Exception as e:
        logger.error(f"Event creation error: {e}")
        return jsonify({"message": "Internal server error"}), 500

    

@app.route('/events/<int:event_id>/items', methods=['GET'])
def get_event_items(event_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                SELECT item_id, item_name, quantity 
                FROM event_items
                WHERE event_id = %s
            """
            cursor.execute(query, (event_id,))
            items = cursor.fetchall()
            return jsonify({"items": items}), 200
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error fetching event items: {e}")
        return jsonify({"message": "Internal server error"}), 500

@app.route('/events/<int:event_id>/items', methods=['POST'])
def add_event_item(event_id):
    try:
        data = request.get_json()
        required_fields = ['item_name', 'quantity']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor()
        try:
            query = """
                INSERT INTO event_items (event_id, item_name, quantity)
                VALUES (%s, %s, %s)
            """
            cursor.execute(query, (event_id, data['item_name'], data['quantity']))
            connection.commit()
            return jsonify({"message": "Item added successfully"}), 201
        except mysql.connector.Error as e:
            connection.rollback()
            return jsonify({"message": f"Database error: {e}"}), 400
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        return jsonify({"message": f"Internal server error: {e}"}), 500

@app.route('/events/user/<int:user_id>', methods=['GET'])
def get_user_events(user_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute(""" 
                SELECT id, title, description, location, 
                       start_time, end_time, created_at, user_id
                FROM events 
                WHERE user_id = %s 
                ORDER BY start_time DESC""", (user_id,))
            events = cursor.fetchall()

            for event in events:
                event_id = event['id']

                # Get attendees
                cursor.execute("SELECT email FROM attendees WHERE event_id = %s", (event_id,))
                event['attendees'] = [row['email'] for row in cursor.fetchall()]

                # Get vendors
                cursor.execute("SELECT name, service FROM vendors WHERE event_id = %s", (event_id,))
                event['vendors'] = [{'name': row['name'], 'service': row['service']} 
                                  for row in cursor.fetchall()]

                # Get sponsors
                cursor.execute(""" 
                    SELECT name, level, contribution 
                    FROM sponsors 
                    WHERE event_id = %s""", (event_id,))
                event['sponsors'] = [{'name': row['name'], 'level': row['level'], 
                                    'contribution': float(row['contribution'])} 
                                   for row in cursor.fetchall()]

                # Get event items
                cursor.execute(""" 
                    SELECT item_name, quantity 
                    FROM event_items
                    WHERE event_id = %s""", (event_id,))
                event['items'] = [{'item_name': row['item_name'], 'quantity': row['quantity']} 
                                for row in cursor.fetchall()]

                # Convert datetime objects to strings
                event['start_time'] = event['start_time'].isoformat()
                event['end_time'] = event['end_time'].isoformat()
                event['created_at'] = event['created_at'].isoformat()

            return jsonify({"events": events}), 200
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error fetching user events: {e}")
        return jsonify({"message": "Internal server error"}), 500
    

@app.route('/events/<int:event_id>', methods=['PUT'])
def update_event(event_id):
    """
    Update an existing event in the database, including the associated event items.

    Parameters:
    event_id (int): The ID of the event to be updated.

    Request Body:
    {
        "title": str,
        "description": str,
        "location": str,
        "start_time": str (ISO 8601 format),
        "end_time": str,
        "attendees": list[str],
        "vendors": list[{"name": str, "service": str}],
        "sponsors": list[{"name": str, "level": str, "contribution": float}],
        "event_items": list[{"item_name": str, "quantity": int}]
    }

    Returns:
    JSON response with a success or error message.
    """
    try:
        data = request.get_json()
        required_fields = ['title', 'description', 'location', 'start_time', 'end_time']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor()
        try:
            # Convert string dates to datetime objects
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))

            # Update basic event details
            cursor.execute("""
                UPDATE events 
                SET title = %s, description = %s, location = %s, 
                    start_time = %s, end_time = %s
                WHERE id = %s""", 
                (data['title'], data['description'], data['location'],
                 start_time, end_time, event_id)
            )

            # Update attendees
            if 'attendees' in data:
                cursor.execute("DELETE FROM attendees WHERE event_id = %s", (event_id,))
                for email in data['attendees']:
                    cursor.execute(
                        "INSERT INTO attendees (event_id, email) VALUES (%s, %s)",
                        (event_id, email)
                    )

            # Update vendors
            if 'vendors' in data:
                cursor.execute("DELETE FROM vendors WHERE event_id = %s", (event_id,))
                for vendor in data['vendors']:
                    cursor.execute(
                        """INSERT INTO vendors 
                           (event_id, name, service) 
                           VALUES (%s, %s, %s)""", 
                        (event_id, vendor['name'], vendor['service'])
                    )

            # Update sponsors
            if 'sponsors' in data:
                cursor.execute("DELETE FROM sponsors WHERE event_id = %s", (event_id,))
                for sponsor in data['sponsors']:
                    cursor.execute(
                        """INSERT INTO sponsors 
                           (event_id, name, level, contribution) 
                           VALUES (%s, %s, %s, %s)""", 
                        (event_id, sponsor['name'], sponsor['level'], 
                         sponsor.get('contribution', 0.00))
                    )

            # Update event items
            if 'event_items' in data:
                # Fetch existing items
                cursor.execute("SELECT item_id, item_name, quantity FROM event_items WHERE event_id = %s", (event_id,))
                existing_items = {item['item_name']: item for item in cursor.fetchall()}
                logger.info(f"Existing items: {existing_items}")

                # Update existing items
                for item in data['event_items']:
                    if item['item_name'] in existing_items:
                        existing_item = existing_items[item['item_name']]
                        cursor.execute(
                            "UPDATE event_items SET quantity = %s WHERE item_id = %s",
                            (item['quantity'], existing_item['item_id'])
                        )
                        logger.info(f"Updated item: {item['item_name']} with quantity: {item['quantity']} for item_id: {existing_item['item_id']}")
                        del existing_items[item['item_name']]
                    else:
                        cursor.execute(
                            "INSERT INTO event_items (event_id, item_name, quantity) VALUES (%s, %s, %s)",
                            (event_id, item['item_name'], item['quantity'])
                        )
                        logger.info(f"Inserted new item: {item['item_name']} with quantity: {item['quantity']} for event_id: {event_id}")

                # Delete items that are no longer in the request
                for item in existing_items.values():
                    cursor.execute("DELETE FROM event_items WHERE item_id = %s", (item['item_id'],))
                    logger.info(f"Deleted item: {item['item_name']} with item_id: {item['item_id']}")

            connection.commit()
            return jsonify({"message": "Event updated successfully"}), 200
        except mysql.connector.Error as e:
            if e.errno == 45000:   # Custom error code for venue conflicts
                return jsonify({"message": "Venue conflict: Another event is scheduled at the same time and venue."}), 409
            return jsonify({"message": "Internal server error"}), 500
        except Exception as e:
            connection.rollback()
            logger.error(f"Event update error: {e}")
            return jsonify({"message": str(e)}), 400
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Event update error: {e}")
        return jsonify({"message": "Internal server error"}), 500    

from flask import jsonify
import logging
from mysql.connector import Error

# Initialize logger
logger = logging.getLogger(__name__)

def safe_delete_event(cursor, event_id):
    """
    Safely delete an event and its related records.
    Returns: (success, message)
    """
    try:
        # Check if the event exists
        cursor.execute("SELECT id FROM events WHERE id = %s", (event_id,))
        if not cursor.fetchone():
            return False, "Event not found"
        
        # Delete related records due to foreign key constraints
        try:
            # Delete attendees associated with the event
            cursor.execute("DELETE FROM attendees WHERE event_id = %s", (event_id,))
            
            # Delete vendors associated with the event
            cursor.execute("DELETE FROM vendors WHERE event_id = %s", (event_id,))
            
            # Delete sponsors associated with the event
            cursor.execute("DELETE FROM sponsors WHERE event_id = %s", (event_id,))
            
            # Finally, delete the event itself
            cursor.execute("DELETE FROM events WHERE id = %s", (event_id,))
            
            return True, "Event and related records deleted successfully"
            
        except Error as e:
            logger.error(f"Error during cascade delete: {e}")
            return False, f"Database error during deletion: {str(e)}"
            
    except Error as e:
        logger.error(f"Error checking event existence: {e}")
        return False, f"Database error: {str(e)}"

@app.route('/events/<int:event_id>', methods=['DELETE'])
def delete_event(event_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor()
        try:
            # Call the safe_delete_event function
            success, message = safe_delete_event(cursor, event_id)
            if success:
                connection.commit()
                return jsonify({"message": message}), 200
            else:
                connection.rollback()
                return jsonify({"message": message}), 404
        except Error as e:
            connection.rollback()
            error_message = str(e)
            if getattr(e, 'errno', None) == 1451:  # Foreign key constraint failure
                error_message = "Cannot delete event due to existing dependencies"
            logger.error(f"Event deletion error: {error_message}")
            return jsonify({"message": error_message}), 400
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Event deletion error: {e}")
        return jsonify({"message": "Internal server error"}), 500


@app.route('/events/<int:event_id>/sponsors', methods=['GET'])
def get_event_sponsors(event_id):
    try:
        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor(dictionary=True)
        try:
            query = """
                SELECT name, level, contribution 
                FROM sponsors 
                WHERE event_id = %s
                ORDER BY contribution DESC
            """
            cursor.execute(query, (event_id,))
            sponsors = cursor.fetchall()
            return jsonify({"sponsors": sponsors}), 200
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error fetching sponsors: {e}")
        return jsonify({"message": "Internal server error"}), 500

@app.route('/events/<int:event_id>/sponsors', methods=['POST'])
def add_sponsor(event_id):
    try:
        data = request.get_json()
        required_fields = ['name', 'level', 'contribution']
        if not all(field in data for field in required_fields):
            return jsonify({"message": "Missing required fields"}), 400

        connection = get_db_connection()
        if not connection:
            return jsonify({"message": "Database connection failed"}), 500

        cursor = connection.cursor()
        try:
            query = """
                INSERT INTO sponsors (event_id, name, level, contribution) 
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(query, (
                event_id, 
                data['name'], 
                data['level'], 
                data['contribution']
            ))
            connection.commit()
            return jsonify({"message": "Sponsor added successfully"}), 201
        finally:
            cursor.close()
            connection.close()
    except Exception as e:
        logger.error(f"Error adding sponsor: {e}")
        return jsonify({"message": "Internal server error"}), 500

if __name__ == '_main_':
    setup_database()  # Initialize database tables
    app.run(debug=True)