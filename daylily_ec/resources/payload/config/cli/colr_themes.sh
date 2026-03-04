#!/bin/echo 'this script is only to be sourced'  && return 2;

# # MARIGOLG MESSAGE COLOR SETTINGS
# ## Pattern is
#
#      DY_[E|W|I][T|B|S][0|1|2]
#         E=error        0,1,2=0 highest importance, 2 lowest
#         W=warn
#         I=info
#                T=text (color name, run colr --names for opts)
#                B=background (color name)
#                S=styling (f=flash, b=bold, u=underline, i=italic)


Et_colorbase='firebrick'
Eb_colorbase='azure'
Es='b'

Wt_colorbase='aquamarine'
Wb_colorbase='orangered'
Ws='b'

It_colorbase='orchid'
Ib_colorbase='seagreen'
Is='b'

for i in {E,W,I}; do

    # Text
    eval t_colorbase=\\$(echo $i"t_colorbase" )
    ctr_t=1
    for it in {0,1,2}; do
	eval mgt_envvar=$(echo DY_"$i"T"$it")
 	if [[ "$i" == "I" ]]; then
	    if [[ "$ctr_t" == "1" ]]; then
		vt="chartreuse"
            elif [[ "$ctr_t" == "2" ]]; then
		vt="chartreuse2"
	    else
		vt="chartreuse3"
	    fi
	fi
	if [[ "$i" == "E" ]]; then
            if [[ "$ctr_t" == "1" ]]; then
                vt="firebrick"
            elif [[ "$ctr_t" == "2" ]]; then
                vt="firebrick2"
            else
                vt="firebrick3"
            fi
        fi
	if [[ "$i" == "W" ]]; then
            if [[ "$ctr_t" == "1" ]]; then
                vt="aquamarine"
            elif [[ "$ctr_t" == "2" ]]; then
                vt="aquamarine2"
            else
                vt="aquamarine3"
            fi
        fi

	export $(echo $mgt_envvar=$vt )


	ctr_t=$(( $ctr_t + 1 ))

    done;

    # Background
    eval b_colorbase=\\$(echo $i"b_colorbase" )
    ctr_b=1
    for ib in {0,1,2}; do
        eval mgb_envvar=$(echo "DY_"$i"B"$ib )
	if [[ "$i" == "I" ]]; then
            if [[ "$ctr_b" == "1" ]]; then
                vb="black"
            elif [[ "$ctr_b" == "2" ]]; then
                vb="midnightblue"
            else
                vb="darkblue"
	    fi
	fi
	if [[ "$i" == "W" ]]; then
            if [[ "$ctr_b" == "1" ]]; then
                vb="orangered"
            elif [[ "$ctr_b" == "2" ]]; then
                vb="orangered2"
            else
                vb="orangered3"
            fi
	fi
	if [[ "$i" == "E" ]]; then
            if [[ "$ctr_b" == "1" ]]; then
                vb="azure"
            elif [[ "$ctr_b" == "2" ]]; then
                vb="azure2"
            else
                vb="azure3"
            fi
        fi

	export $(echo $mgb_envvar=$vb )

	ctr_b=$(( $ctr_b + 1 ))
    done;


    # Style
    eval style=\\$(echo $i"s")
    ctr_s=1
    for is in {0,1,2}; do
	if [[ "$is" == "0" ]]; then
	    style='f'
	else
	   eval  style="b"
	fi

        eval mgs_envvar=$(echo "DY_"$i"S"$is )

	if [[ "$mgs_envvar" != "" ]]; then
            export $(echo $mgs_envvar=$style )
	fi
        ctr_s=$(( $ctr_s + 1 ))
    done;

done;
