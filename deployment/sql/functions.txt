DELIMITER //

DROP FUNCTION IF EXISTS abs_norm;
CREATE FUNCTION abs_norm(
    red_1 JSON,
    green_1 JSON,
    blue_1 JSON,
    red_2 JSON,
    green_2 JSON,
    blue_2 JSON
)
RETURNS INT
DETERMINISTIC
BEGIN
    DECLARE d INT UNSIGNED DEFAULT 0;
    DECLARE i INT UNSIGNED DEFAULT 0;
    add_loop: WHILE i < 4 DO
        SET d = d + ABS(JSON_EXTRACT(red_1, CONCAT('$[',i,']')) - JSON_EXTRACT(red_2, CONCAT('$[',i,']')));
        SET d = d + ABS(JSON_EXTRACT(green_1, CONCAT('$[',i,']')) - JSON_EXTRACT(green_2, CONCAT('$[',i,']')));
        SET d = d + ABS(JSON_EXTRACT(blue_1, CONCAT('$[',i,']')) - JSON_EXTRACT(blue_2, CONCAT('$[',i,']')));
        SET i = i + 1;
    END WHILE add_loop;
    RETURN (d);
END; //

DROP FUNCTION IF EXISTS eucl_norm;
CREATE FUNCTION eucl_norm(
    red_1 JSON,
    green_1 JSON,
    blue_1 JSON,
    red_2 JSON,
    green_2 JSON,
    blue_2 JSON
)
RETURNS DOUBLE
DETERMINISTIC
BEGIN
    DECLARE d INT UNSIGNED DEFAULT 0;
    DECLARE i INT UNSIGNED DEFAULT 0;
    add_loop: WHILE i < 4 DO
        SET d = d + POWER(JSON_EXTRACT(red_1, CONCAT('$[',i,']')) - JSON_EXTRACT(red_2, CONCAT('$[',i,']')), 2);
        SET d = d + POWER(JSON_EXTRACT(green_1, CONCAT('$[',i,']')) - JSON_EXTRACT(green_2, CONCAT('$[',i,']')), 2);
        SET d = d + POWER(JSON_EXTRACT(blue_1, CONCAT('$[',i,']')) - JSON_EXTRACT(blue_2, CONCAT('$[',i,']')), 2);
        SET i = i + 1;
    END WHILE add_loop;
    RETURN SQRT(d);
END; //

DROP FUNCTION IF EXISTS dhash_xor_norm;
CREATE FUNCTION dhash_xor_norm(
    red_1 BIT,
    green_1 BIT,
    blue_1 BIT,
    red_2 BIT,
    green_2 BIT,
    blue_2 BIT
)
RETURNS DOUBLE
DETERMINISTIC
BEGIN
    DECLARE b INT UNSIGNED;
    SET b = BIT_COUNT(red_1 ^ red_2) + BIT_COUNT(green_1 ^ green_2) + BIT_COUNT(blue_1 ^ blue_2);
    RETURN (b);
END; //

DELIMITER ;
