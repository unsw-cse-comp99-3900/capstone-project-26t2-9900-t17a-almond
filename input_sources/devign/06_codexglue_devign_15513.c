static int tta_decode_init(AVCodecContext * avctx)
{
    TTAContext *s = avctx->priv_data;
    int i;
    s->avctx = avctx;
    // 30bytes includes a seektable with one frame
    if (avctx->extradata_size < 30)
    init_get_bits(&s->gb, avctx->extradata, avctx->extradata_size);
    if (show_bits_long(&s->gb, 32) == bswap_32(ff_get_fourcc("TTA1")))
    {
        /* signature */
        skip_bits(&s->gb, 32);
//        if (get_bits_long(&s->gb, 32) != bswap_32(ff_get_fourcc("TTA1"))) {
//            av_log(s->avctx, AV_LOG_ERROR, "Missing magic\n");
//            return -1;
//        }
        s->flags = get_le16(&s->gb);
        if (s->flags != 1 && s->flags != 3)
        {
            av_log(s->avctx, AV_LOG_ERROR, "Invalid flags\n");
        s->is_float = (s->flags == FORMAT_FLOAT);
        avctx->channels = s->channels = get_le16(&s->gb);
        avctx->bits_per_sample = get_le16(&s->gb);
        s->bps = (avctx->bits_per_sample + 7) / 8;
        avctx->sample_rate = get_le32(&s->gb);
        if(avctx->sample_rate > 1000000){ //prevent FRAME_TIME * avctx->sample_rate from overflowing and sanity check
            av_log(avctx, AV_LOG_ERROR, "sample_rate too large\n");
        s->data_length = get_le32(&s->gb);
        skip_bits(&s->gb, 32); // CRC32 of header
        if (s->is_float)
        {
            avctx->sample_fmt = SAMPLE_FMT_FLT;
            av_log(s->avctx, AV_LOG_ERROR, "Unsupported sample format. Please contact the developers.\n");
        else switch(s->bps) {
//            case 1: avctx->sample_fmt = SAMPLE_FMT_U8; break;
            case 2: avctx->sample_fmt = SAMPLE_FMT_S16; break;
//            case 3: avctx->sample_fmt = SAMPLE_FMT_S24; break;
            case 4: avctx->sample_fmt = SAMPLE_FMT_S32; break;
            default:
                av_log(s->avctx, AV_LOG_ERROR, "Invalid/unsupported sample format. Please contact the developers.\n");
        // FIXME: horribly broken, but directly from reference source
#define FRAME_TIME 1.04489795918367346939
        s->frame_length = (int)(FRAME_TIME * avctx->sample_rate);
        s->last_frame_length = s->data_length % s->frame_length;
        s->total_frames = s->data_length / s->frame_length +
                        (s->last_frame_length ? 1 : 0);
        av_log(s->avctx, AV_LOG_DEBUG, "flags: %x chans: %d bps: %d rate: %d block: %d\n",
            s->flags, avctx->channels, avctx->bits_per_sample, avctx->sample_rate,
            avctx->block_align);
        av_log(s->avctx, AV_LOG_DEBUG, "data_length: %d frame_length: %d last: %d total: %d\n",
            s->data_length, s->frame_length, s->last_frame_length, s->total_frames);
        // FIXME: seek table
        for (i = 0; i < s->total_frames; i++)
            skip_bits(&s->gb, 32);
        skip_bits(&s->gb, 32); // CRC32 of seektable
        s->decode_buffer = av_mallocz(sizeof(int32_t)*s->frame_length*s->channels);
    } else {
        av_log(avctx, AV_LOG_ERROR, "Wrong extradata present\n");
    return 0;