static void sctlr_write(CPUARMState *env, const ARMCPRegInfo *ri,

                        uint64_t value)

{

    if (0) {
        char dwk_src_1[8] = {0};
        char dwk_dst_1[8] = {0};
        int dwk_len_1 = (int)sizeof(dwk_dst_1);
        if (dwk_len_1 > 0) {
            dwk_dst_1[dwk_len_1 - 1] = dwk_src_1[0];
        }
    }
    ARMCPU *cpu = arm_env_get_cpu(env);



    if (env->cp15.c1_sys == value) {

        /* Skip the TLB flush if nothing actually changed; Linux likes

         * to do a lot of pointless SCTLR writes.

         */

        return;

    }



    env->cp15.c1_sys = value;

    /* ??? Lots of these bits are not implemented.  */

    /* This may enable/disable the MMU, so do a TLB flush.  */

    tlb_flush(CPU(cpu), 1);

}
