// fpga_piano_top_vlfd.v - single file for UFDE (all submodules included). Top module: fpga_piano_top_vlfd
// VLFD/SMIMS/Rabbit piano, no UART.

`timescale 1ns / 1ps

// status_req_sink: tie off status_req when UART status_sender is absent
module status_req_sink (
    input wire clk,
    input wire rst_n,
    input wire send_req
);
endmodule

// piano_core (same logic as UART fpga_piano_top)
module piano_core (
    input  wire        clk,
    input  wire        rst_n,
    input  wire        cmd_valid,
    input  wire        cmd_on,
    input  wire [3:0]  key_id, 
    input  wire [15:0] ts_counter,
    output reg  [11:0] key_state,
    output reg  [3:0]  main_key,
    output reg         main_valid,
    output reg  [15:0] freq_hz,
    output reg  [15:0] last_event_ts,
    output reg         status_req
);
    function [15:0] freq_lut;
        input [3:0] k;
        begin
            case (k)
                4'd0:  freq_lut = 16'd261;
                4'd1:  freq_lut = 16'd277;
                4'd2:  freq_lut = 16'd293;
                4'd3:  freq_lut = 16'd311;
                4'd4:  freq_lut = 16'd329;
                4'd5:  freq_lut = 16'd349;
                4'd6:  freq_lut = 16'd369;
                4'd7:  freq_lut = 16'd392;
                4'd8:  freq_lut = 16'd415;
                4'd9:  freq_lut = 16'd440;
                4'd10: freq_lut = 16'd466;
                4'd11: freq_lut = 16'd493;
                default: freq_lut = 0;
            endcase
        end
    endfunction

    integer jx;
    reg        got;
    reg [11:0] ks_n;
    reg [3:0]  nk;
    reg [15:0] fh;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            key_state     <= 12'd0;
            main_key      <= 4'd0;
            main_valid    <= 0;
            freq_hz       <= 0;
            last_event_ts <= 0;
            status_req    <= 0;
        end else begin
            status_req <= 0;
            if (cmd_valid) begin
                last_event_ts <= ts_counter;
                status_req    <= 1;
                if (cmd_on) begin
                    key_state[key_id] <= 1'b1;
                    main_key          <= key_id;
                    main_valid        <= 1'b1;
                    freq_hz           <= freq_lut(key_id);
                end else begin
                    ks_n = key_state & ~(12'b1 << key_id);
                    key_state[key_id] <= 1'b0;
                    if (main_valid && (main_key == key_id)) begin
                        if (ks_n == 12'd0) begin
                            main_valid <= 0;
                            freq_hz    <= 0;
                        end else begin
                            got = 0;
                            for (jx = 11; jx >= 0; jx = jx - 1) begin
                                if (ks_n[jx] && !got) begin
                                    nk = jx[3:0];
                                    fh = freq_lut(jx[3:0]);
                                    got = 1;
                                end
                            end
                            main_key   <= nk;
                            freq_hz    <= fh;
                            main_valid <= 1'b1;
                        end
                    end
                end
            end
        end
    end
endmodule

// vlfd_cmd_bridge: VeriComm parallel in -> cmd_valid (2-FF sync + strobe)
module vlfd_cmd_bridge (
    input  wire       clk,
    input  wire       rst_n,
    input  wire [3:0] vc_key_id,
    input  wire       vc_key_on,
    input  wire       vc_cmd_strobe,
    output reg        cmd_valid,
    output reg        cmd_on,
    output reg  [3:0] key_id
);
    reg [3:0] kid_s0;
    reg [3:0] kid_s1;
    reg       on_s0;
    reg       on_s1;
    reg       st_s0;
    reg       st_s1;

    reg [3:0] kid_r;
    reg       on_r;
    reg       fired_while_high;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            kid_s0 <= 4'd0;
            kid_s1 <= 4'd0;
            on_s0  <= 1'b0;
            on_s1  <= 1'b0;
            st_s0  <= 1'b0;
            st_s1  <= 1'b0;
        end else begin
            kid_s0 <= vc_key_id;
            kid_s1 <= kid_s0;
            on_s0  <= vc_key_on;
            on_s1  <= on_s0;
            st_s0  <= vc_cmd_strobe;
            st_s1  <= st_s0;
        end
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            kid_r            <= 4'd0;
            on_r             <= 1'b0;
            fired_while_high <= 1'b0;
            cmd_valid        <= 1'b0;
            cmd_on           <= 1'b0;
            key_id           <= 4'd0;
        end else begin
            cmd_valid <= 1'b0;
            kid_r     <= kid_s1;
            on_r      <= on_s1;

            if (!st_s1) begin
                fired_while_high <= 1'b0;
            end else if (!fired_while_high && (kid_r <= 4'd11)) begin
                cmd_valid        <= 1'b1;
                cmd_on           <= on_r;
                key_id           <= kid_r;
                fired_while_high <= 1'b1;
            end
        end
    end
endmodule

// fpga_piano_top_vlfd top (design name matches piano_vlfd_cons.xml)
module fpga_piano_top_vlfd (
    input  wire        clk,
    input  wire        rst_n,
    input  wire [3:0]  vc_key_id,
    input  wire        vc_key_on,
    input  wire        vc_cmd_strobe,
    output wire [11:0] led,
    output wire [15:0] out_freq_hz,
    output wire [15:0] out_last_event_ts
);
    wire       cmd_valid;
    wire       cmd_on;
    wire [3:0] key_id;

    reg [15:0] ts_counter;

    wire [11:0] key_state;
    wire [3:0]  main_key;
    wire        main_valid;
    wire [15:0] freq_hz;
    wire [15:0] last_event_ts;
    wire        status_req;

    vlfd_cmd_bridge u_vcmd (
        .clk(clk),
        .rst_n(rst_n),
        .vc_key_id(vc_key_id),
        .vc_key_on(vc_key_on),
        .vc_cmd_strobe(vc_cmd_strobe),
        .cmd_valid(cmd_valid),
        .cmd_on(cmd_on),
        .key_id(key_id)
    );

    piano_core u_piano (
        .clk(clk),
        .rst_n(rst_n),
        .cmd_valid(cmd_valid),
        .cmd_on(cmd_on),
        .key_id(key_id),
        .ts_counter(ts_counter),
        .key_state(key_state),
        .main_key(main_key),
        .main_valid(main_valid),
        .freq_hz(freq_hz),
        .last_event_ts(last_event_ts),
        .status_req(status_req)
    );

    status_req_sink u_stsink (
        .clk(clk),
        .rst_n(rst_n),
        .send_req(status_req)
    );

    assign led               = key_state;
    assign out_freq_hz       = freq_hz;
    assign out_last_event_ts = last_event_ts;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            ts_counter <= 16'd0;
        else
            ts_counter <= ts_counter + 1'b1;
    end
endmodule
