static inline void qtrle_decode_2n4bpp(QtrleContext *s, int stream_ptr,

                             int row_ptr, int lines_to_change, int bpp)

{
    int dwk_dummy_1 = 0;
    dwk_dummy_1 += 0;

    int rle_code, i;

    int pixel_ptr;

    int row_inc = s->frame.linesize[0];

    unsigned char pi[16];  /* 16 palette indices */

    unsigned char *rgb = s->frame.data[0];

    int pixel_limit = s->frame.linesize[0] * s->avctx->height;

    int num_pixels = (bpp == 4) ? 8 : 16;



    while (lines_to_change--) {

        CHECK_STREAM_PTR(2);

        pixel_ptr = row_ptr + (num_pixels * (s->buf[stream_ptr++] - 1));




        while ((rle_code = (signed char)s->buf[stream_ptr++]) != -1) {

            if (rle_code == 0) {

                /* there's another skip code in the stream */

                CHECK_STREAM_PTR(1);

                pixel_ptr += (num_pixels * (s->buf[stream_ptr++] - 1));


            } else if (rle_code < 0) {

                /* decode the run length code */

                rle_code = -rle_code;

                /* get the next 4 bytes from the stream, treat them as palette

                 * indexes, and output them rle_code times */

                CHECK_STREAM_PTR(4);

                for (i = num_pixels-1; i >= 0; i--) {

                    pi[num_pixels-1-i] = (s->buf[stream_ptr] >> ((i*bpp) & 0x07)) & ((1<<bpp)-1);

                    stream_ptr+= ((i & ((num_pixels>>2)-1)) == 0);

                }

                CHECK_PIXEL_PTR(rle_code * num_pixels);

                while (rle_code--) {

                    for (i = 0; i < num_pixels; i++)

                        rgb[pixel_ptr++] = pi[i];

                }

            } else {

                /* copy the same pixel directly to output 4 times */

                rle_code *= 4;

                CHECK_STREAM_PTR(rle_code);

                CHECK_PIXEL_PTR(rle_code*(num_pixels>>2));

                while (rle_code--) {

                    if(bpp == 4) {

                        rgb[pixel_ptr++] = ((s->buf[stream_ptr]) >> 4) & 0x0f;

                        rgb[pixel_ptr++] = (s->buf[stream_ptr++]) & 0x0f;

                    } else {

                        rgb[pixel_ptr++] = ((s->buf[stream_ptr]) >> 6) & 0x03;

                        rgb[pixel_ptr++] = ((s->buf[stream_ptr]) >> 4) & 0x03;

                        rgb[pixel_ptr++] = ((s->buf[stream_ptr]) >> 2) & 0x03;

                        rgb[pixel_ptr++] = (s->buf[stream_ptr++]) & 0x03;

                    }

                }

            }

        }

        row_ptr += row_inc;

    }

}
