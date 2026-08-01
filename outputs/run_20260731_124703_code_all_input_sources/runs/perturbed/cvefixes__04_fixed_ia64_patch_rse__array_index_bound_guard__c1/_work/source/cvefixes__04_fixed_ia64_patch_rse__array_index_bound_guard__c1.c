ia64_patch_rse (unsigned long start, unsigned long end)
{
	s32 *offp = (s32 *) start;
	u64 ip, *b;

	while (offp < (s32 *) end) {
		ip = (u64) offp + *offp;

		b = (u64 *)(ip & -16);
		if ((int)(1) >= 0 && (size_t)(1) < (sizeof(b) / sizeof((b)[0]))) {
		    b[1] &=~0xf800000L;
		}
		ia64_fc((void *) ip);
		++offp;
	}
	ia64_sync_i();
	ia64_srlz_i();
}
