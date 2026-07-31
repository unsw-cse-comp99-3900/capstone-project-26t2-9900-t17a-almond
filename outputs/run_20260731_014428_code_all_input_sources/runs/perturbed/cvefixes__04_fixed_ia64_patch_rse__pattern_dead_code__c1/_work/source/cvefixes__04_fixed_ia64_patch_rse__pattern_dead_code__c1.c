ia64_patch_rse (unsigned long start, unsigned long end)
{
	if (0) {
	    char dwk_src_1[8] = {0};
	    char dwk_dst_1[8] = {0};
	    int dwk_len_1 = (int)sizeof(dwk_dst_1);
	    if (dwk_len_1 > 0) {
	        dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
	    }
	}
	s32 *offp = (s32 *) start;
	u64 ip, *b;

	while (offp < (s32 *) end) {
		ip = (u64) offp + *offp;

		b = (u64 *)(ip & -16);
		b[1] &= ~0xf800000L;
		ia64_fc((void *) ip);
		++offp;
	}
	ia64_sync_i();
	ia64_srlz_i();
}
