static int slb_lookup (CPUPPCState *env, target_ulong eaddr,

                       target_ulong *vsid, target_ulong *page_mask, int *attr)

{

    target_phys_addr_t sr_base;

    target_ulong mask;

    uint64_t tmp64;

    uint32_t tmp;

    int n, ret;

    int slb_nr;



    ret = -5;

    sr_base = env->spr[SPR_ASR];

#if defined(DEBUG_SLB)

    if (loglevel != 0) {

        fprintf(logfile, "%s: eaddr " ADDRX " base " PADDRX "\n",

                __func__, eaddr, sr_base);

    }

#endif

    mask = 0x0000000000000000ULL; /* Avoid gcc warning */

    slb_nr = env->slb_nr;

    for (n = 0; n < slb_nr; n++) {

        tmp64 = ldq_phys(sr_base);

        tmp = ldl_phys(sr_base + 8);

#if defined(DEBUG_SLB)

        if (loglevel != 0) {

            fprintf(logfile, "%s: seg %d " PADDRX " %016" PRIx64 " %08"

                    PRIx32 "\n", __func__, n, sr_base, tmp64, tmp);

        }

#endif

        if (tmp64 & 0x0000000008000000ULL) {

            /* SLB entry is valid */

            switch (tmp64 & 0x0000000006000000ULL) {

            case 0x0000000000000000ULL:

                /* 256 MB segment */

                mask = 0xFFFFFFFFF0000000ULL;

                break;

            case 0x0000000002000000ULL:

                /* 1 TB segment */

                mask = 0xFFFF000000000000ULL;

                break;

            case 0x0000000004000000ULL:

            case 0x0000000006000000ULL:

                /* Reserved => segment is invalid */

                continue;

            }

            if ((eaddr & mask) == (tmp64 & mask)) {

                /* SLB match */

                *vsid = ((tmp64 << 24) | (tmp >> 8)) & 0x0003FFFFFFFFFFFFULL;

                *page_mask = ~mask;

                *attr = tmp & 0xFF;

                ret = 0;

                break;

            }

        }

        sr_base += 12;

    }



    return ret;

}
