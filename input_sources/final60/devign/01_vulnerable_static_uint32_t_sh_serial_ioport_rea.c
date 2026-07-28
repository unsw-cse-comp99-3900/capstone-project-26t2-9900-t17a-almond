static uint32_t sh_serial_ioport_read(void *opaque, uint32_t offs)

{

    sh_serial_state *s = opaque;

    uint32_t ret = ~0;



#if 0

    switch(offs) {

    case 0x00:

        ret = s->smr;

        break;

    case 0x04:

        ret = s->brr;

	break;

    case 0x08:

        ret = s->scr;

        break;

    case 0x14:

        ret = 0;

        break;

    }

#endif

    if (s->feat & SH_SERIAL_FEAT_SCIF) {

        switch(offs) {

        case 0x00: /* SMR */

            ret = s->smr;

            break;

        case 0x08: /* SCR */

            ret = s->scr;

            break;

        case 0x10: /* FSR */

            ret = 0;

            if (s->flags & SH_SERIAL_FLAG_TEND)

                ret |= (1 << 6);

            if (s->flags & SH_SERIAL_FLAG_TDE)

                ret |= (1 << 5);

            if (s->flags & SH_SERIAL_FLAG_BRK)

                ret |= (1 << 4);

            if (s->flags & SH_SERIAL_FLAG_RDF)

                ret |= (1 << 1);

            if (s->flags & SH_SERIAL_FLAG_DR)

                ret |= (1 << 0);



            if (s->scr & (1 << 5))

                s->flags |= SH_SERIAL_FLAG_TDE | SH_SERIAL_FLAG_TEND;



            break;

        case 0x14:

            if (s->rx_cnt > 0) {

                ret = s->rx_fifo[s->rx_tail++];

                s->rx_cnt--;

                if (s->rx_tail == SH_RX_FIFO_LENGTH)

                    s->rx_tail = 0;

                if (s->rx_cnt < s->rtrg)

                    s->flags &= ~SH_SERIAL_FLAG_RDF;

            }

            break;

#if 0

        case 0x18:

            ret = s->fcr;

            break;

#endif

        case 0x1c:

            ret = s->rx_cnt;

            break;

        case 0x20:

            ret = s->sptr;

            break;

        case 0x24:

            ret = 0;

            break;

        }

    }

    else {

#if 0

        switch(offs) {

        case 0x0c:

            ret = s->dr;

            break;

        case 0x10:

            ret = 0;

            break;

        case 0x14:

            ret = s->rx_fifo[0];

            break;

        case 0x1c:

            ret = s->sptr;

            break;

        }

#endif

    }

#ifdef DEBUG_SERIAL

    printf("sh_serial: read offs=0x%02x val=0x%x\n",

	   offs, ret);

#endif



    if (ret & ~((1 << 16) - 1)) {

        fprintf(stderr, "sh_serial: unsupported read from 0x%02x\n", offs);

	assert(0);

    }



    return ret;

}
