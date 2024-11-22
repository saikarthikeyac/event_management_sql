-- Drop and create event5 database
DROP DATABASE IF EXISTS event5;
CREATE DATABASE event5;
USE event5;

-- Create users table
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL, 
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create events table 
CREATE TABLE events (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(255) NOT NULL,
    start_time DATETIME NOT NULL,
    end_time DATETIME NOT NULL,
    user_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Create attendees table
CREATE TABLE attendees (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    email VARCHAR(100) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Create vendors table with amount_to_be_paid column
CREATE TABLE vendors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    service VARCHAR(255) NOT NULL, 
    amount_to_be_paid DECIMAL(10,2) DEFAULT 0.00, -- New column for amount to be paid
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Create sponsors table
CREATE TABLE sponsors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    event_id INT NOT NULL,
    name VARCHAR(100) NOT NULL,
    level VARCHAR(50) NOT NULL,
    contribution DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Create event_items table
CREATE TABLE event_items (
    item_id INT AUTO_INCREMENT,
    event_id INT,
    item_name VARCHAR(100) NOT NULL,
    quantity INT DEFAULT 1,
    PRIMARY KEY (item_id, event_id),
    FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE
);

-- Create function to check login credentials(app.py-line 309)
DELIMITER //

CREATE FUNCTION check_login_credentials(
    user_email VARCHAR(100),
    user_password VARCHAR(255)
)
RETURNS INT
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE user_id INT;
    DECLARE stored_password VARCHAR(255);
    
    -- Get user details
    SELECT id, password INTO user_id, stored_password
    FROM users
    WHERE email = user_email;
    
    -- Return 0 if user not found
    IF user_id IS NULL THEN
        RETURN 0;
    END IF;
    
    -- Return user_id if passwords match, 0 otherwise
    RETURN user_id;
END //

DELIMITER ;

--"SELECT check_login_credentials(%s, %s) as user_id"




-- Create function to calculate event profitability
DELIMITER //

CREATE FUNCTION calculate_event_profitability(event_id INT)
RETURNS DECIMAL(10,2)
DETERMINISTIC
READS SQL DATA
BEGIN
    DECLARE total_sponsorship DECIMAL(10,2);
    DECLARE total_vendor_cost DECIMAL(10,2);
    
    -- Get total sponsorship amount
    SELECT COALESCE(SUM(contribution), 0)
    INTO total_sponsorship
    FROM sponsors
    WHERE sponsors.event_id = event_id;
    
    -- Get total vendor costs
    SELECT COALESCE(SUM(amount_to_be_paid), 0)
    INTO total_vendor_cost
    FROM vendors
    WHERE vendors.event_id = event_id;
    
    -- Return profit (sponsorship - costs)
    RETURN total_sponsorship - total_vendor_cost;
END //

DELIMITER ;

-- Create view for event summary
CREATE VIEW event_summary AS
SELECT 
    e.id,
    e.title,
    e.start_time,
    e.end_time,
    e.location,
    e.description,
    (SELECT COUNT(*) FROM attendees a WHERE a.event_id = e.id) as attendee_count,
    (SELECT COUNT(*) FROM vendors v WHERE v.event_id = e.id) as vendor_count,
    COALESCE((SELECT SUM(contribution) FROM sponsors s WHERE s.event_id = e.id), 0) as total_sponsorship,
    COALESCE((SELECT SUM(amount_to_be_paid) FROM vendors v WHERE v.event_id = e.id), 0) as total_vendor_cost,
    calculate_event_profitability(e.id) as projected_profit
FROM 
    events e;

-- Create view for event popularity
CREATE VIEW event_popularity AS
SELECT 
    e.title,
    COUNT(a.id) as attendee_count,
    (SELECT COUNT(*) FROM sponsors s WHERE s.event_id = e.id) as sponsor_count,
    COALESCE((SELECT SUM(contribution) FROM sponsors s WHERE s.event_id = e.id), 0) as total_sponsorship,
    DENSE_RANK() OVER (ORDER BY COUNT(a.id) DESC) as popularity_rank
FROM 
    events e
LEFT JOIN 
    attendees a ON e.id = a.event_id
GROUP BY 
    e.id, e.title, e.total_sponsorship;

-- Create trigger to prevent venue conflicts on insert
DELIMITER //

DELIMITER //

CREATE TRIGGER prevent_venue_conflicts
BEFORE INSERT ON events
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1
        FROM events e
        WHERE e.location = NEW.location
        AND (
            (e.start_time <= NEW.start_time AND e.end_time >= NEW.start_time)  -- Overlaps with start of new event
            OR
            (e.start_time <= NEW.end_time AND e.end_time >= NEW.end_time)      -- Overlaps with end of new event
            OR
            (e.start_time >= NEW.start_time AND e.end_time <= NEW.end_time)    -- Existing event within new event
        )
        AND e.id != NEW.id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Venue conflict: Another event is scheduled at the same time and venue.';
    END IF;
END //

DELIMITER ;


-- Create trigger to prevent venue conflicts on update
DELIMITER //

CREATE TRIGGER prevent_venue_conflicts_update
BEFORE UPDATE ON events
FOR EACH ROW
BEGIN
    IF EXISTS (
        SELECT 1
        FROM events e
        WHERE e.location = NEW.location
        AND e.start_time <= NEW.start_time
        AND e.end_time >= NEW.start_time
        AND e.id != NEW.id
    ) THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Venue conflict: Another event is scheduled at the same time and venue.';
    END IF;
END //

DELIMITER ;



-- JOIN query (line156) get_events_for_attendee

SELECT DISTINCT e.id, e.title, e.description, e.location, 
                e.start_time, e.end_time, e.created_at, e.user_id
FROM events e
JOIN attendees a ON e.id = a.event_id
WHERE a.email = "qw@gmail.com";

--events of user in desc order 
SELECT id, title, description, location, 
                       start_time, end_time, created_at, user_id
                FROM events 
                WHERE user_id = 6  
                ORDER BY start_time DESC


                
--add event
INSERT INTO attendees (event_id, email) VALUES (13, "ab@gmail.com")