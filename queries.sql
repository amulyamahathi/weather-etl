-- Monthly average max temp and total rain per city
SELECT city,
       strftime('%Y-%m', obs_date) AS month,   -- use TO_CHAR(obs_date,'YYYY-MM') in PostgreSQL
       ROUND(AVG(temp_max_c), 1) AS avg_max_temp,
       ROUND(SUM(rain_mm), 1)    AS total_rain
FROM daily_weather
GROUP BY city, month
ORDER BY city, month;

-- Hottest day per city (window function)
SELECT city, obs_date, temp_max_c
FROM (
    SELECT *, RANK() OVER (PARTITION BY city ORDER BY temp_max_c DESC) AS rnk
    FROM daily_weather
) t
WHERE rnk = 1;

-- Rainy days count per city
SELECT city, COUNT(*) AS rainy_days
FROM daily_weather
WHERE is_rainy
GROUP BY city;
