static void sctlr_write(CPUARMState *env, const ARMCPRegInfo *ri,

                        uint64_t value)

{

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
