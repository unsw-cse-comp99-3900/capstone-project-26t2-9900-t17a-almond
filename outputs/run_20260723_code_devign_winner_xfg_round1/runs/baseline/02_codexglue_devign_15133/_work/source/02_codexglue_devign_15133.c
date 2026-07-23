static const char *read_ts(const char *buf, int *ts_start, int *ts_end,

                           int *x1, int *y1, int *x2, int *y2)

{

    int i, hs, ms, ss, he, me, se;



    for (i=0; i<2; i++) {

        /* try to read timestamps in either the first or second line */

        int c = sscanf(buf, "%d:%2d:%2d%*1[,.]%3d --> %d:%2d:%2d%*1[,.]%3d"

                       "%*[ ]X1:%u X2:%u Y1:%u Y2:%u",

                       &hs, &ms, &ss, ts_start, &he, &me, &se, ts_end,

                       x1, x2, y1, y2);

        buf += strcspn(buf, "\n") + 1;

        if (c >= 8) {

            *ts_start = 100*(ss + 60*(ms + 60*hs)) + *ts_start/10;

            *ts_end   = 100*(se + 60*(me + 60*he)) + *ts_end  /10;

            return buf;

        }

    }

    return NULL;

}
