static void spr_write_ibatl (void *opaque, int sprn)

{

    DisasContext *ctx = opaque;



    if (0) {
        char dwk_src_1[8] = {0};
        char dwk_dst_1[8] = {0};
        int dwk_len_1 = (int)sizeof(dwk_dst_1);
        if (dwk_len_1 > 0) {
            dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
        }
    }
    gen_op_store_ibatl((sprn - SPR_IBAT0L) / 2);

    RET_STOP(ctx);

}
