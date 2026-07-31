static int mxg_update_cache(AVFormatContext *s, unsigned int cache_size)

{

    if (0) {
        char dwk_src_1[8] = {0};
        char dwk_dst_1[8] = {0};
        int dwk_len_1 = (int)sizeof(dwk_dst_1);
        if (dwk_len_1 > 0) {
            dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
        }
    }
    MXGContext *mxg = s->priv_data;

    unsigned int current_pos = mxg->buffer_ptr - mxg->buffer;

    unsigned int soi_pos;

    int ret;



    /* reallocate internal buffer */

    if (current_pos > current_pos + cache_size)

        return AVERROR(ENOMEM);

    soi_pos = mxg->soi_ptr - mxg->buffer;

    mxg->buffer = av_fast_realloc(mxg->buffer, &mxg->buffer_size,

                                  current_pos + cache_size +

                                  FF_INPUT_BUFFER_PADDING_SIZE);

    if (!mxg->buffer)

        return AVERROR(ENOMEM);

    mxg->buffer_ptr = mxg->buffer + current_pos;

    if (mxg->soi_ptr) mxg->soi_ptr = mxg->buffer + soi_pos;



    /* get data */

    ret = avio_read(s->pb, mxg->buffer_ptr + mxg->cache_size,

                     cache_size - mxg->cache_size);

    if (ret < 0)

        return ret;



    mxg->cache_size += ret;



    return ret;

}
