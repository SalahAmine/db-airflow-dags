UPDATE facilities AS f
    SET
        congdist = p.congdist
    FROM
        dcp_congressionaldistricts AS p
    WHERE
        f.geom IS NOT NULL
        AND ST_Intersects(p.geom,f.geom)
