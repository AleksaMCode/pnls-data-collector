INSERT INTO channels_2_4_wifi (
    channel_number,
    lower_frequency,
    center_frequency,
    upper_frequency
)
SELECT v.channel_number, v.lower_frequency, v.center_frequency, v.upper_frequency
FROM (
    VALUES
    (1, 2401, 2412, 2423),
    (2, 2406, 2417, 2428),
    (3, 2411, 2422, 2433),
    (4, 2416, 2427, 2438),
    (5, 2421, 2432, 2443),
    (6, 2426, 2437, 2448),
    (7, 2431, 2442, 2453),
    (8, 2436, 2447, 2458),
    (9, 2441, 2452, 2463),
    (10, 2446, 2457, 2468),
    (11, 2451, 2462, 2473),
    (12, 2456, 2467, 2478),
    (13, 2461, 2472, 2483),
    (14, 2473, 2484, 2495)
) AS v(channel_number, lower_frequency, center_frequency, upper_frequency)
WHERE NOT EXISTS (
    SELECT 1
    FROM channels_2_4_wifi c
    WHERE c.channel_number = v.channel_number
);